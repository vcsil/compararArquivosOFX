# Benchmark de leitura e escrita — Etapa 1

Ambiente: Linux x86-64, Python 3.12.14, AMD EPYC 9V74 (5 CPUs visíveis). Executar `venv/bin/python tests/benchmark_etapa1.py`. Dez repetições por cenário, `perf_counter_ns`, mediana/mínimo/máximo em ms. O arquivo sintético é criado antes das medições; leitura de bytes, detecção/decodificação, parsing/conversão e serialização são medidas separadamente. A escrita usa bytes pré-serializados, arquivo temporário local e cache do SO, sem fsync; não é medição de durabilidade. Não representa processamento completo nem inicialização Windows. Sem controle de carga, os resultados são indicativos.

| Cenário | Mediana (ms) | Mínimo | Máximo |
|---|---:|---:|---:|
| 100 leitura bytes | 0.007 | 0.005 | 0.147 |
| 100 formato e codificação | 0.042 | 0.032 | 0.135 |
| 100 parsing e conversão | 71.589 | 67.621 | 76.099 |
| 100 serialização | 9.499 | 8.756 | 16.554 |
| 100 escrita bytes | 0.248 | 0.085 | 1.152 |
| 1000 leitura bytes | 0.008 | 0.007 | 0.081 |
| 1000 formato e codificação | 0.118 | 0.101 | 0.560 |
| 1000 parsing e conversão | 688.192 | 628.925 | 814.888 |
| 1000 serialização | 81.832 | 80.991 | 90.545 |
| 1000 escrita bytes | 0.220 | 0.147 | 0.572 |
| 10000 leitura bytes | 0.041 | 0.038 | 0.182 |
| 10000 formato e codificação | 0.819 | 0.787 | 1.616 |
| 10000 parsing e conversão | 6935.739 | 6854.329 | 7688.874 |
| 10000 serialização | 945.004 | 915.732 | 1006.030 |
| 10000 escrita bytes | 3.193 | 0.558 | 4.542 |

A baseline da Etapa 0 mediu parse e conversão de 1.000 em 701,341 ms e serialização com gravação em 118,244 ms. Nesta execução, detecção + parsing totalizam aproximadamente 688,310 ms (soma de medianas separadas, não mediana conjunta), e serialização + escrita aproximadamente 82,052 ms. Os métodos diferem, portanto a comparação é indicativa, não um ganho estatisticamente comprovado. O parser/conversão do ofxtools domina os tempos medidos; identificação de encoding e I/O em cache são pequenos em comparação. Para 10.000 transações o parse por si só supera a meta futura de um segundo. Investigar representação e conversão em uma etapa posterior, preservando validação e precisão.

A importação tardia pode acelerar a primeira interação, mas transfere o custo para a leitura e não foi implementada nem medida nesta etapa. Medições de executável Windows e comparação entre empacotadores continuam pendentes para a Etapa 5.

## Revisão 1.1: duas decodificações estritas

Mesmo comando e dez repetições por cenário; dados sintéticos ASCII com cabeçalho 1252. Mediana, mínimo e máximo em ms:

| Cenário | Mediana | Mínimo | Máximo |
|---|---:|---:|---:|
| 100 leitura bytes | 0.005 | 0.005 | 0.139 |
| 100 formato e codificação | 0.042 | 0.038 | 0.128 |
| 100 parsing e conversão | 65.147 | 63.692 | 78.775 |
| 100 serialização | 8.776 | 8.532 | 15.461 |
| 100 escrita bytes | 0.205 | 0.079 | 0.448 |
| 1000 leitura bytes | 0.008 | 0.007 | 0.087 |
| 1000 formato e codificação | 0.164 | 0.161 | 0.331 |
| 1000 parsing e conversão | 670.482 | 658.744 | 688.400 |
| 1000 serialização | 93.804 | 89.185 | 99.550 |
| 1000 escrita bytes | 0.240 | 0.172 | 0.699 |
| 10000 leitura bytes | 0.047 | 0.044 | 0.236 |
| 10000 formato e codificação | 1.457 | 1.407 | 2.159 |
| 10000 parsing e conversão | 6962.432 | 6546.430 | 7372.059 |
| 10000 serialização | 950.868 | 873.408 | 1049.794 |
| 10000 escrita bytes | 2.964 | 0.592 | 3.858 |

Para 1.000 transações a detecção passou de 0,118 para 0,164 ms e para 10.000 de 0,819 para 1,457 ms, em execuções separadas. Parsing de 1.000 foi 670,482 ms ante 688,192 ms; essas diferenças isoladas não demonstram mudança estatisticamente significativa. O benchmark não inclui tratamento interativo nem dados ambíguos. O parser continua dominante; a comparação não mede inicialização Windows.
