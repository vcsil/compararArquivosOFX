import platform, statistics, tempfile, time
from pathlib import Path
from test_baseline import fixture
from controller.ofx_io import preparar_ofx, interpretar_ofx, serializar_ofx

def measure(label, function):
    samples=[]
    for _ in range(10):
        start=time.perf_counter_ns(); function(); samples.append((time.perf_counter_ns()-start)/1e6)
    print(f'{label}: {statistics.median(samples):.3f} {min(samples):.3f} {max(samples):.3f}',flush=True)

print(platform.platform(),platform.python_version(),flush=True)
with tempfile.TemporaryDirectory() as tmp:
    p=Path(tmp)/'entrada.ofx'; out=Path(tmp)/'saida.ofx'
    for n in (100,1000,10000):
        data=fixture([('20230102120000','20',str(i),f'Memo {i}') for i in range(n)])
        p.write_bytes(data)
        fmt,head,body=preparar_ofx(data)
        model=interpretar_ofx(fmt,body)
        encoded=serializar_ofx(model)
        measure(f'{n} leitura bytes',p.read_bytes)
        measure(f'{n} formato e codificação',lambda: preparar_ofx(data))
        measure(f'{n} parsing e conversão',lambda: interpretar_ofx(fmt,body))
        measure(f'{n} serialização',lambda: serializar_ofx(model))
        measure(f'{n} escrita bytes',lambda: out.write_bytes(encoded))
