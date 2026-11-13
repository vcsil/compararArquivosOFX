# Benchmark do motor — Etapa 2

Linux x86-64, Python 3.12.14, AMD EPYC 9V74 (5 CPUs visíveis). `PYTHONPATH=src venv/bin/python tests/benchmark_etapa2.py`; dados e modelos sintéticos pré-construídos, dez repetições, tempo em ms, sem parser, serialização ou construção do modelo filtrado. A tabela do novo motor é de uma repetição posterior após acrescentar verificações de CHECKNUM e precisão Decimal; o antigo é da primeira execução no mesmo ambiente. O antigo não inclui remoção do modelo nem validações.

| Tamanho | Cenário | Estado novo | Novo mediana | Mínimo | Máximo | Antigo mediana |
|---:|---|---|---:|---:|---:|---:|
| 100 | nenhuma | BLOQUEADO | 0.261 | 0.198 | 0.546 | 0.410 |
| 100 | todas | SEM_NOVIDADES | 0.281 | 0.250 | 0.419 | 0.030 |
| 100 | parte | APROVADO | 0.367 | 0.316 | 0.747 | 0.031 |
| 100 | iguais | APROVADO | 0.433 | 0.371 | 0.576 | 0.036 |
| 100 | fora_ordem | SEM_NOVIDADES | 0.265 | 0.251 | 0.438 | 0.028 |
| 1000 | nenhuma | BLOQUEADO | 2.070 | 1.888 | 2.534 | 26.865 |
| 1000 | todas | SEM_NOVIDADES | 2.571 | 2.452 | 2.807 | 0.440 |
| 1000 | parte | APROVADO | 3.277 | 3.033 | 3.505 | 0.612 |
| 1000 | iguais | APROVADO | 3.971 | 3.927 | 5.056 | 0.716 |
| 1000 | fora_ordem | SEM_NOVIDADES | 2.518 | 2.368 | 2.739 | 0.570 |
| 10000 | nenhuma | BLOQUEADO | 21.193 | 20.329 | 23.211 | 2565.104 |
| 10000 | todas | SEM_NOVIDADES | 27.564 | 26.223 | 30.612 | não medido |
| 10000 | parte | APROVADO | 35.405 | 32.834 | 37.962 | não medido |
| 10000 | iguais | APROVADO | 42.810 | 41.878 | 54.495 | não medido |
| 10000 | fora_ordem | SEM_NOVIDADES | 27.491 | 26.253 | 31.810 | não medido |
| 50000 | nenhuma | BLOQUEADO | 122.037 | 116.260 | 125.844 | não medido |
| 50000 | todas | SEM_NOVIDADES | 149.284 | 137.888 | 216.611 | não medido |
| 50000 | parte | APROVADO | 182.050 | 177.558 | 187.803 | não medido |
| 50000 | iguais | APROVADO | 219.979 | 214.265 | 235.414 | não medido |
| 50000 | fora_ordem | SEM_NOVIDADES | 141.071 | 138.155 | 151.180 | não medido |

O antigo compara descrição e valor, enquanto o novo usa FITID, valida contas e confere totais. Portanto não são operações equivalentes: especialmente em `iguais`, o antigo descarta movimentações distintas. Em `nenhuma`, o novo bloqueia cedo por falta dos FITIDs de referência, enquanto o antigo percorre todas as combinações. Os números não estabelecem aceleração de processamento completo com mesmo resultado. Os testes em 10.000 e 50.000 com o antigo, salvo 10.000 sem correspondência, não foram medidos devido ao custo quadrático. Em `parte` e `iguais` são acrescentadas respectivamente 50% e 100% de novas transações ao tamanho indicado para o histórico. A meta de 50 ms para o motor isolado de 10.000 foi atingida nesta máquina para os cenários executados, sem incluir cópia, parser ou I/O.
