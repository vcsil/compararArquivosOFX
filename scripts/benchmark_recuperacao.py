"""Mede recuperação sintética após publicação do Geral, sem tempo de preparação."""
import statistics, sys, tempfile, time
from datetime import date
from pathlib import Path
from unittest.mock import patch
repo=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(repo/'tests'))
from test_baseline import fixture
from controller import safe_storage as ss
from controller.workflow import planejar, executar
from controller.organization import pasta_dia

samples=[]
with tempfile.TemporaryDirectory() as tmp:
    for n in range(10):
        root=Path(tmp)/str(n); root.mkdir(); bank=root/'Banco'; bank.mkdir(); day=pasta_dia(bank,date(2026,11,12)); day.mkdir(parents=True)
        old=('20261110120000','10','A','Sintetico'); new=('20261111120000','20','B','Sintetico')
        (day/'OFXGeral-2026-11-12.ofx').write_bytes(fixture([old]))
        src=root/'entrada.ofx'; src.write_bytes(fixture([old,new]))
        plan=planejar(root,bank,src,hoje=date(2026,11,12)); real=ss.publicar_arquivo
        def interrupt(*args):
            real(*args); raise OSError('interrupção sintética')
        with patch.object(ss,'publicar_arquivo',side_effect=interrupt):
            try: executar(plan)
            except OSError: pass
            else: raise AssertionError('interrupção não ocorreu')
        with ss.bloquear(bank):
            start=time.perf_counter_ns(); ss.recuperar_concluida(bank); samples.append((time.perf_counter_ns()-start)/1e6)
        if src.exists() or ss.pendencias(bank): raise AssertionError('recuperação incompleta')
print(f'recuperação n={len(samples)} mediana={statistics.median(samples):.3f} min={min(samples):.3f} max={max(samples):.3f} ms')
