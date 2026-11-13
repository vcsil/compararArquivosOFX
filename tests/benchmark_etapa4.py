"""Medição sintética de preparação, publicação e importação segura."""
import contextlib
import platform
import statistics
import tempfile
import time
from datetime import date
from pathlib import Path
from unittest.mock import patch
from test_baseline import fixture
from controller import workflow, safe_storage, ofx_functions
from controller.ofx_names import eh_nome_limpo


def stats(values):
    return f'mediana={statistics.median(values):.3f} min={min(values):.3f} max={max(values):.3f} ms n={len(values)}'

print(platform.platform(),platform.python_version(),flush=True)
for n in (100,1000):
    samples={x:[] for x in ('lock','hash','temporarios','validacao_ofx','publicar_pasta','publicar_geral','finalizacao','total')}
    payload=fixture([('20261110120000','10',str(i),'Teste') for i in range(n)])
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp)
        for i in range(10):
            work=root/str(i); work.mkdir(); bank=work/'Banco'; bank.mkdir(); source=work/'entrada.ofx'; source.write_bytes(payload)
            grouped={k:0 for k in samples}
            def timed(name, func):
                def wrapper(*args,**kwargs):
                    start=time.perf_counter_ns()
                    try: return func(*args,**kwargs)
                    finally: grouped[name]+=(time.perf_counter_ns()-start)/1e6
                return wrapper
            oldlock=safe_storage.bloquear
            @contextlib.contextmanager
            def lock(*args,**kwargs):
                start=time.perf_counter_ns(); cm=oldlock(*args,**kwargs); token=cm.__enter__()
                grouped['lock']+=(time.perf_counter_ns()-start)/1e6
                try: yield token
                finally: cm.__exit__(None,None,None)
            oldread=ofx_functions.carregar_ofx
            def read(path,*args,**kwargs):
                if (eh_nome_limpo(Path(path).name) or Path(path).name == 'geral.tmp'):
                    return timed('validacao_ofx',oldread)(path,*args,**kwargs)
                return oldread(path,*args,**kwargs)
            start=time.perf_counter_ns()
            with patch.object(safe_storage,'bloquear',lock), patch.object(workflow,'_hash',timed('hash',workflow._hash)), \
                 patch.object(safe_storage,'escrever',timed('temporarios',safe_storage.escrever)), \
                 patch.object(safe_storage,'publicar_pasta',timed('publicar_pasta',safe_storage.publicar_pasta)), \
                 patch.object(safe_storage,'publicar_arquivo',timed('publicar_geral',safe_storage.publicar_arquivo)), \
                 patch.object(safe_storage,'finalizar',timed('finalizacao',safe_storage.finalizar)), \
                 patch.object(ofx_functions,'carregar_ofx',read):
                with safe_storage.bloquear(bank) as token:
                    plano=workflow.planejar(work,bank,source,hoje=date(2026,11,12)); workflow.executar(plano,bloqueio=token)
            grouped['total']=(time.perf_counter_ns()-start)/1e6
            for name in samples: samples[name].append(grouped[name])
    for name,values in samples.items(): print(n,name,stats(values),flush=True)
