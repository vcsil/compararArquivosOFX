"""Comparações sintéticas; sem parse nem criação de modelo no tempo medido."""
import platform, statistics, time
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace as NS
from controller.ofx_comparison import analisar

def stmt(trans):
    account=NS(bankid='1',acctid='123',accttype='CHECKING')
    return NS(statements=[NS(bankacctfrom=account,curdef='BRL',transactions=trans)],signonmsgsrsv1=None)
def make(n,pattern):
    dt=datetime(2023,1,2,12,tzinfo=timezone.utc)
    old=[NS(fitid=str(i),trnamt=Decimal('1'),trntype='CREDIT',memo='comum',dtposted=dt) for i in range(n)]
    # A inclusão integral do dia de referência é obrigatória para aprovação.
    if pattern=='todas': new=list(old)
    elif pattern=='parte': new=list(old)+[NS(fitid=f'n{i}',trnamt=Decimal('1'),trntype='CREDIT',memo='comum',dtposted=dt) for i in range(n//2)]
    elif pattern=='iguais': new=list(old)+[NS(fitid=f'n{i}',trnamt=Decimal('1'),trntype='CREDIT',memo='comum',dtposted=dt) for i in range(n)]
    elif pattern=='fora_ordem': new=list(reversed(old))
    else: new=[NS(fitid=f'n{i}',trnamt=Decimal('1'),trntype='CREDIT',memo='outro',dtposted=dt) for i in range(n)]
    return old,new

def antigo(old,new):
    anteriores=[((t.memo,t.trnamt),t.fitid) for t in old]
    atuais=[[(t.memo,t.trnamt),t.fitid] for t in new]
    for anterior,_ in anteriores:
        for nova,ident in atuais:
            if anterior == nova:
                atuais.remove([nova,ident]); break

def medir(fn,n=10):
    times=[]
    for _ in range(n):
        start=time.perf_counter_ns(); fn(); times.append((time.perf_counter_ns()-start)/1e6)
    return f'{statistics.median(times):.3f} {min(times):.3f} {max(times):.3f}'

if __name__=='__main__':
    print(platform.platform(),platform.python_version(),flush=True)
    for n in (100,1000,10000,50000):
        for pattern in ('nenhuma','todas','parte','iguais','fora_ordem'):
            old,new=make(n,pattern); previous,current=stmt(old),stmt(new)
            r=analisar(current,previous)
            print(n,pattern,'novo',r.relatorio.estado,medir(lambda:analisar(current,previous)),flush=True)
            # Quadrático: limita custo de execução. 10.000 sem correspondências
            # é medido 10 vezes, demais grandes ficam explicitamente pendentes.
            if n<=1000 or (n==10000 and pattern=='nenhuma'):
                print(n,pattern,'antigo',medir(lambda:antigo(old,new)),flush=True)
            else: print(n,pattern,'antigo nao medido',flush=True)
