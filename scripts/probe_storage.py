"""Diagnóstico sintético de lock local. Não homologa sincronização entre dispositivos."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from controller.safe_storage import bloquear
from controller.organization import OrganizacaoError


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('diretorio', type=Path)
    args=parser.parse_args()
    result={'dados_financeiros':'NAO_UTILIZADOS','entre_dispositivos':'NAO_HOMOLOGADO'}
    with tempfile.TemporaryDirectory(prefix='compara-storage-probe-',dir=args.diretorio) as tmp:
        bank=Path(tmp)/'Banco Sintetico';bank.mkdir()
        try:
            with bloquear(bank):pass
        except OrganizacaoError as exc:
            result['lock_local']='BLOQUEADO';result['diagnostico']=str(exc)
            print(json.dumps(result,ensure_ascii=False));return 1
        lock=next((bank.parent/'.comparaofx-locks').iterdir())
        result['st_nlink_lock']=lock.stat().st_nlink
        code="from pathlib import Path; from controller.safe_storage import bloquear; import sys\nwith bloquear(Path(sys.argv[1])):\n print('READY',flush=True)\n sys.stdin.readline()"
        env=os.environ.copy();env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src')
        child=subprocess.Popen([sys.executable,'-c',code,str(bank)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
        try:
            if child.stdout.readline().strip()!='READY':raise RuntimeError('Processo de teste não iniciou')
            try:
                with bloquear(bank):pass
            except OrganizacaoError:result['concorrencia_mesma_maquina']='BLOQUEADA_CORRETAMENTE'
            else:raise RuntimeError('Exclusão mútua não demonstrada')
        finally:child.communicate('\n',timeout=15)
        result['lock_local']='VERIFICADO_APENAS_NESTA_MAQUINA'
    print(json.dumps(result,ensure_ascii=False,indent=2));return 0


if __name__=='__main__':sys.exit(main())
