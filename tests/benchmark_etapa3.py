"""Medições sintéticas sem espera por entrada; requer PYTHONPATH=src."""
import platform, statistics, subprocess, sys, tempfile, time
from datetime import date, timedelta
from pathlib import Path
from test_baseline import fixture
from controller.organization import instituicoes, extratos, localizar_historico, pasta_dia
from controller.workflow import planejar, executar

def measure(label, fn, n=10):
    values=[]
    for i in range(n):
        start=time.perf_counter_ns(); fn(i); values.append((time.perf_counter_ns()-start)/1e6)
    print(f'{label}: mediana={statistics.median(values):.3f} min={min(values):.3f} max={max(values):.3f} ms n={n}',flush=True)
print(platform.platform(),platform.python_version(),flush=True)
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp); bank=root/'Banco'; bank.mkdir(); today=date(2026,11,12)
    data=fixture([('20261110120000','10',str(i),'Teste') for i in range(100)])
    for i in range(20):
        day=today-timedelta(days=i+1); path=pasta_dia(bank,day); path.mkdir(parents=True,exist_ok=True)
        (path/f'OFXGeral-{day.isoformat()}.ofx').write_bytes(data)
    measure('instituições',lambda _:instituicoes(root))
    (root/'input.ofx').write_bytes(data)
    measure('extratos',lambda _:extratos(root))
    measure('histórico com 20 dias',lambda _:localizar_historico(bank,today))
    cli="import sys; sys.path.insert(0, 'src'); from comparaArqOFX import main; main(sys.argv[1])"
    def first_menu(_):
        proc=subprocess.Popen([sys.executable,'-u','-c',cli,str(root)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            while True:
                line=proc.stdout.readline()
                if not line: raise RuntimeError('processo sem menu')
                if line.strip()=='00 - Cancelar': break
        finally:
            proc.stdin.write('0\n'); proc.stdin.flush(); proc.communicate(timeout=10)
    measure('processo Python até primeiro menu',first_menu)
    roots=[]
    for i in range(10):
        r=root/f'flow{i}'; r.mkdir(); b=r/'Banco'; b.mkdir(); s=r/'input.ofx'; s.write_bytes(data); roots.append((r,b,s))
    def flow(i):
        r,b,s=roots[i]; executar(planejar(r,b,s,hoje=today))
    measure('primeira importação 100 transações',flow)
