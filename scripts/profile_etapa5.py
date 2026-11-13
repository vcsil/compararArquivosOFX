"""Perfil sintético em Linux/Windows; sem logs de movimentações."""
import argparse
import hashlib
import platform
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(repo/'tests'))
from test_baseline import fixture
from controller.ofx_functions import carregar_ofx
from controller.ofx_io import serializar_ofx, interpretar_ofx
from controller.ofx_comparison import analisar
from controller.workflow import planejar, executar

def timed(label, fn):
    start=time.perf_counter_ns(); value=fn(); duration=(time.perf_counter_ns()-start)/1e6
    print(f'{label}: {duration:.3f} ms',flush=True); return value

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--sizes',nargs='+',type=int,default=[100,1000,10000]); args=parser.parse_args()
    print(platform.platform(),platform.python_version(),flush=True)
    with tempfile.TemporaryDirectory() as tmp:
        base=Path(tmp)
        for size in args.sizes:
            root=base/str(size); root.mkdir(); bank=root/'Banco'; bank.mkdir(); source=root/'entrada.ofx'
            payload=fixture([('20261110120000','10',str(i),'Sintetico') for i in range(size)])
            source.write_bytes(payload)
            print('transações:',size,flush=True)
            raw=timed('leitura bytes',source.read_bytes)
            timed('hash SHA256',lambda: hashlib.sha256(raw).digest())
            _,ofx=timed('leitura e conversão inicial',lambda: carregar_ofx(source))
            result=timed('análise primeira importação',lambda: analisar(ofx))
            filtered=timed('construção modelo filtrado',lambda: result.modelo_filtrado(ofx))
            encoded=timed('serialização',lambda:serializar_ofx(filtered))
            timed('conversão da saída',lambda: interpretar_ofx('xml',encoded))
            def flow():
                return executar(planejar(root,bank,source,hoje=date(2026,11,12)))
            timed('fluxo íntegro planejamento e execução',flow)

if __name__=='__main__': main()
