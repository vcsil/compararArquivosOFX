"""Benchmark sintético do fluxo seguro; valores por etapa podem se sobrepor."""
import argparse
import contextlib
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from datetime import date
from pathlib import Path
from unittest.mock import patch

repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(repo/'tests'))
from test_baseline import fixture
from controller import ofx_comparison, ofx_functions, ofx_io, safe_storage, workflow


def one(n, memory=False):
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp); bank=root/'Banco'; bank.mkdir(); source=root/'Entrada.ofx'
        source.write_bytes(fixture([('20261110120000','10',str(i),'Sintetico') for i in range(n)]))
        values={name:0.0 for name in ('leitura','analise','filtragem','serializacao','validacao_leitura','assinaturas','escrita_publicacao')}
        def timed(name,fn):
            def wrapper(*args,**kwargs):
                start=time.perf_counter()
                try: return fn(*args,**kwargs)
                finally: values[name]+=time.perf_counter()-start
            return wrapper
        oldread=ofx_functions.carregar_ofx
        def read(path,*args,**kwargs):
            name='validacao_leitura' if Path(path).name=='geral.tmp' or Path(path).name.startswith('OFX Limpo-') else 'leitura'
            return timed(name,oldread)(path,*args,**kwargs)
        if memory: tracemalloc.start()
        start=time.perf_counter()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(ofx_functions,'carregar_ofx',read))
            stack.enter_context(patch.object(ofx_comparison,'analisar',timed('analise',ofx_comparison.analisar)))
            stack.enter_context(patch.object(ofx_comparison.Resultado,'modelo_filtrado',timed('filtragem',ofx_comparison.Resultado.modelo_filtrado)))
            stack.enter_context(patch.object(ofx_io,'serializar_ofx',timed('serializacao',ofx_io.serializar_ofx)))
            stack.enter_context(patch.object(workflow,'_assinatura',timed('assinaturas',workflow._assinatura)))
            for name in ('escrever','publicar_pasta','publicar_arquivo','finalizar'):
                stack.enter_context(patch.object(safe_storage,name,timed('escrita_publicacao',getattr(safe_storage,name))))
            plan=workflow.planejar(root,bank,source,hoje=date(2026,11,13)); dest=workflow.executar(plan)
        values['total']=time.perf_counter()-start
        values['pico_bytes']=tracemalloc.get_traced_memory()[1] if memory else None
        if memory: tracemalloc.stop()
        assert (dest/'Entrada.ofx').is_file() and len(oldread(plan.geral)[1].statements[0].transactions)==n
        return values


def recovery(n):
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp); bank=root/'Banco';bank.mkdir();source=root/'Entrada.ofx'
        source.write_bytes(fixture([('20261110120000','10',str(i),'Sintetico') for i in range(n)]))
        plan=workflow.planejar(root,bank,source,hoje=date(2026,11,13));old=safe_storage.publicar_arquivo
        def interrupt(*args): old(*args); raise OSError('interrupcao sintetica')
        try:
            with patch.object(safe_storage,'publicar_arquivo',side_effect=interrupt): workflow.executar(plan)
        except OSError as exc:
            if str(exc)!='interrupcao sintetica': raise
        else: raise AssertionError('Interrupção não exercitada')
        start=time.perf_counter();safe_storage.recuperar_concluida(bank);elapsed=time.perf_counter()-start
        assert not source.exists() and (plan.importacao/'Entrada.ofx').is_file()
        return elapsed


def main():
    p=argparse.ArgumentParser();p.add_argument('--repeticoes',type=int,default=2);p.add_argument('--tamanhos',type=int,nargs='+',default=[100,1000,10000]);p.add_argument('--memoria',action='store_true');p.add_argument('--somente-recuperacao',action='store_true');a=p.parse_args()
    if a.repeticoes<2: p.error('São necessárias pelo menos duas repetições')
    print(json.dumps({'python':sys.version.split()[0],'platform':platform.platform(),'repeticoes':a.repeticoes,'memory':'tracemalloc: apenas alocações Python, uma execução separada' if a.memoria else 'não medida'}),flush=True)
    for n in a.tamanhos:
        if a.somente_recuperacao:
            times=[recovery(n) for _ in range(a.repeticoes)]
            print(json.dumps({'transacoes':n,'recuperacao_n':len(times),'mediana_s':statistics.median(times)}),flush=True)
            continue
        runs=[one(n) for _ in range(a.repeticoes)]
        result={k:statistics.median(x[k] for x in runs) for k in runs[0] if k!='pico_bytes'}
        if a.memoria: result['pico_bytes']=one(n,True)['pico_bytes']
        result['transacoes']=n;print(json.dumps(result),flush=True)

if __name__=='__main__': main()
