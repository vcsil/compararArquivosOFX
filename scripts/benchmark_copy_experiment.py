"""Experimento sintético; a cópia estrutural demonstrada NÃO é segura para produção."""
import argparse
import copy
import statistics
import sys
import tempfile
import time
import tracemalloc
from datetime import datetime, timedelta, tzinfo
from decimal import Decimal
from pathlib import Path

repo=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(repo/'tests'))
from test_baseline import fixture
from controller.ofx_functions import carregar_ofx
from controller.ofx_comparison import analisar
from controller.ofx_io import serializar_ofx
from controller.workflow import _assinatura


def clone_experimental(obj, selected):
    # Demonstração deliberadamente não usada na aplicação: acessa internos do ofxtools.
    memo={}; target=obj.statements[0].transactions
    def clone(x):
        key=id(x)
        if key in memo: return memo[key]
        cls=type(x)
        if cls.__module__.startswith('ofxtools.models'):
            if isinstance(x,list):
                y=list.__new__(cls); memo[key]=y
                for z in ([x[i] for i in selected] if x is target else x): list.append(y,clone(z))
            else:
                y=object.__new__(cls); memo[key]=y
            y.__dict__.update({key:clone(value) for key,value in x.__dict__.items()})
            return y
        if isinstance(x,list):
            y=[]; memo[key]=y; y.extend(clone(z) for z in x); return y
        if isinstance(x,dict):
            y={}; memo[key]=y; y.update((clone(k),clone(v)) for k,v in x.items()); return y
        return copy.deepcopy(x,memo)
    return clone(obj)


def verify_independence(candidate, original):
    before=_assinatura(original)
    statement=candidate.statements[0]
    if statement.transactions:
        item=statement.transactions[0]
        item.fitid='alterado'; item.memo='alterado'; item.trnamt=Decimal('999')
        item.dtposted=datetime(2026,11,12,12,tzinfo=item.dtposted.tzinfo)
        statement.transactions.pop()
    statement.bankacctfrom.acctid='999'
    statement.banktranlist.dtstart=datetime(2020,1,1,tzinfo=statement.banktranlist.dtstart.tzinfo)
    statement.ledgerbal.balamt=Decimal('999')
    if _assinatura(original)!=before: raise AssertionError('Modelo original alterado')


def timezone_counterexample():
    class MutableTZ(tzinfo):
        def __init__(self): self.offset=timedelta(hours=-3)
        def utcoffset(self,dt): return self.offset
        def dst(self,dt): return timedelta(0)
        def tzname(self,dt): return 'EST'
        def __deepcopy__(self,memo): return self
    with tempfile.TemporaryDirectory() as tmp:
        path=Path(tmp)/'exemplo.ofx';path.write_bytes(fixture([('20261110120000','10','1','Sintetico')]))
        model=carregar_ofx(path)[1]
        model.statements[0].transactions[0].dtposted=datetime(2026,11,10,12,tzinfo=MutableTZ())
        result=analisar(model); assert result.relatorio.estado!='BLOQUEADO'
        baseline=result.modelo_filtrado(model)
        candidate=clone_experimental(model,result.indices_novos)
        candidate.statements[0].transactions[0].dtposted.tzinfo.offset=timedelta(hours=-2)
        assert model.statements[0].transactions[0].dtposted.utcoffset()==timedelta(hours=-2)
        assert baseline.statements[0].transactions[0].dtposted.utcoffset()==timedelta(hours=-3)
        print('CONTRAEXEMPLO: fuso mutável compartilhado pelo protótipo; baseline permanece independente.',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repeticoes',type=int,default=2)
    parser.add_argument('--tamanhos',type=int,nargs='+',default=[100,1000,10000])
    args=parser.parse_args()
    if args.repeticoes<2 or any(n<2 for n in args.tamanhos): parser.error('Use ao menos duas repetições e duas transações.')
    print('Python',sys.version.split()[0],flush=True)
    timezone_counterexample()
    for n in args.tamanhos:
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'sintetico.ofx'
            source.write_bytes(fixture([('20261110120000','10',str(i),'Sintetico') for i in range(n)]))
            original=carregar_ofx(source)[1]; result=analisar(original)
            result.indices_novos=tuple(range(0,n,2))
            reference=None
            for label,operation in (('serializacao',lambda:result.modelo_filtrado(original)),
                                    ('deepcopy',lambda:copy.deepcopy(original)),
                                    ('estrutural',lambda:clone_experimental(original,result.indices_novos))):
                times=[]; peaks=[]
                for _ in range(args.repeticoes):
                    tracemalloc.start(); started=time.perf_counter()
                    try: model=operation()
                    except Exception as exc:
                        tracemalloc.stop(); print(n,label,'ERRO',type(exc).__name__,str(exc),flush=True); break
                    times.append(time.perf_counter()-started); peaks.append(tracemalloc.get_traced_memory()[1]);tracemalloc.stop()
                    serial=serializar_ofx(model)
                    if label=='serializacao': reference=serial
                    elif serial!=reference: raise AssertionError('OFX serializado divergente')
                    verify_independence(model,original)
                else:
                    print(n,label,'n',len(times),'mediana_s',round(statistics.median(times),4),'pico_bytes',max(peaks),flush=True)

if __name__=='__main__': main()
