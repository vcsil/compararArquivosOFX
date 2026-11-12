import copy, io, os, platform, statistics, subprocess, sys, tempfile, time
from pathlib import Path
from test_baseline import A, fixture, parse
from controller import ofx_functions as f

def measure(name, fn, n=10):
    samples=[]
    for _ in range(n):
        t=time.perf_counter_ns(); fn(); samples.append((time.perf_counter_ns()-t)/1e6)
    print(f'{name}: mediana={statistics.median(samples):.3f} ms min={min(samples):.3f} ms max={max(samples):.3f} ms n={n}',flush=True)
print(platform.platform(),platform.python_version(),flush=True)
# Processo novo com bibliotecas e cache do sistema aquecidos; inclui inicialização do Python.
measure('processo Python + import ofxtools.Parser',lambda: subprocess.run([sys.executable,'-c','import ofxtools.Parser'],stdout=subprocess.DEVNULL,check=True))
items=[('20230102120000','20',str(i),f'Memo {i}') for i in range(1000)]
data=fixture(items)
measure('parse e conversão SGML 1000',lambda:parse(data))
# Reprodução do laço de comparação da aplicação: sem correspondências, pior caso;
# listas construídas antes do cronômetro, sem incluir parser ou geração.
for n in (100,1000,10000):
    old=[((f'old {i}',20),str(i)) for i in range(n)]
    new=[[(f'new {i}',20),str(i)] for i in range(n)]
    def compare():
        for previous,_ in old:
            for current,ident in new:
                if previous == current: break
    measure(f'comparação {n} sem correspondências',compare)
with tempfile.TemporaryDirectory() as tmp:
    o=parse(data)
    output_dir = Path(tmp)/'out'
    output_dir.mkdir()
    indices = iter(range(10))
    measure('serialização e escrita 1000',lambda:f.salvar_ofx(o,'header',str(output_dir),f'result-{next(indices)}.ofx'))
