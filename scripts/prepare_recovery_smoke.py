"""Prepara dados sintéticos persistentes para homologação sem Python no destino.

Execute na máquina de desenvolvimento. O destino deve ser novo; não há remoção
ou alteração de históricos existentes, nem executável incluído no pacote.
"""
import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(repo/'tests'))
from test_baseline import fixture
from controller import safe_storage as ss
from controller.workflow import planejar, executar
from controller.ofx_names import LEGADO_LIMPO


class InterrupcaoSintetica(RuntimeError):
    pass


def preparar(destino):
    destino=Path(destino)
    destino.mkdir(parents=True,exist_ok=False)
    cases=[]
    raw=fixture([('20261110120000','20','SYNTH-1','Sintetico')])
    for version in (1,2):
        for stage in ('preparado','geral','parcial'):
            root=destino/f'v{version}-{stage}'; root.mkdir()
            bank=root/'Banco Sintetico'; bank.mkdir()
            source=root/'Entrada.ofx'; source.write_bytes(raw)
            attachment=root/'Comprovante.pdf'; attachment.write_bytes(b'PDF sintetico')
            plan=planejar(root,bank,source,[attachment],hoje=date.today())
            real_publish=ss.publicar_arquivo; real_unlink=Path.unlink
            def publish(*args):
                real_publish(*args)
                raise InterrupcaoSintetica()
            def unlink(path,*args,**kwargs):
                is_source=path.exists() and path.samefile(source)
                result=real_unlink(path,*args,**kwargs)
                if is_source: raise InterrupcaoSintetica()
                return result
            if stage=='preparado':
                fault=patch.object(ss,'publicar_pasta',side_effect=InterrupcaoSintetica)
            elif stage=='geral':
                fault=patch.object(ss,'publicar_arquivo',side_effect=publish)
            else:
                fault=patch.object(Path,'unlink',unlink)
            try:
                with fault: executar(plan)
            except InterrupcaoSintetica:
                pass
            else:
                raise AssertionError('Ponto de interrupção não exercitado')
            op=ss.pendencias(bank)[0]
            manifest=json.loads((op/'manifesto.json').read_text(encoding='utf-8'))
            clean=(op/'pasta' if stage=='preparado' else plan.importacao)/plan.limpo_nome
            if version==1:
                # Fixture v1, não migração de históricos existentes.
                clean=clean.rename(clean.with_name(LEGADO_LIMPO))
                manifest['versao']=1; manifest.pop('limpo_nome')
                ss.atualizar_manifesto(op,manifest)
            info=(f'Cenario sintetico v{version}, ponto {stage}.\n'
                  'Copie ComparaOFX.exe para esta pasta e abra por duplo clique.\n'
                  'Se houver selecao, escolha 1 (Banco Sintetico).\n'
                  'Confirme credito BRL 20 / FITID SYNTH-1 e original arquivado.\n'
                  f'SHA256 Entrada.ofx: {hashlib.sha256(raw).hexdigest()}\n'
                  f'Nome preparado do Limpo: {clean.name}\n'
                  'Antes da publicacao a preparacao sera limpa e uma nova importacao v2 ocorrera.\n'
                  'Apos publicacao os nomes arquivados devem permanecer inalterados.\n')
            (root/'LEIA-ME.txt').write_text(info,encoding='utf-8')
            cases.append(root)
    return cases


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destino',type=Path,help='Diretorio novo para seis cenarios sinteticos')
    args=parser.parse_args()
    for case in preparar(args.destino): print(case)
