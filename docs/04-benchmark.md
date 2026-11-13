# Benchmark de integridade — Etapa 4

Linux x86-64, Python 3.12.14, AMD EPYC 9V74 (5 CPUs visíveis), diretório temporário local, sem controle de cache de disco. `PYTHONPATH=src venv/bin/python tests/benchmark_etapa4.py`; dez execuções por cenário, mediana/mínimo/máximo em milissegundos. Tempos por fase são instrumentados em torno das funções e podem se sobrepor; temporários incluem escrita e fsync dos manifestos e OFX, mas não toda a cópia. Total inclui planejamento, validação, cópia, publicação e limpeza; não inclui geração dos dados ou espera por usuário. Não mede falta de energia, rede, antivírus ou Windows.

```text
Linux-6.18.57-x86_64-with-glibc2.41 3.12.14
100 lock mediana=0.347 min=0.210 max=0.651 ms n=10
100 hash mediana=0.477 min=0.434 max=0.542 ms n=10
100 temporarios mediana=6.306 min=5.645 max=6.979 ms n=10
100 validacao_ofx mediana=136.613 min=131.350 max=154.491 ms n=10
100 publicar_pasta mediana=0.694 min=0.562 max=2.383 ms n=10
100 publicar_geral mediana=0.280 min=0.184 max=0.501 ms n=10
100 finalizacao mediana=0.260 min=0.213 max=0.411 ms n=10
100 total mediana=309.286 min=301.259 max=333.589 ms n=10
1000 lock mediana=0.364 min=0.204 max=0.478 ms n=10
1000 hash mediana=1.534 min=1.351 max=1.786 ms n=10
1000 temporarios mediana=8.291 min=6.403 max=33.843 ms n=10
1000 validacao_ofx mediana=1321.666 min=1205.097 max=1491.605 ms n=10
1000 publicar_pasta mediana=0.805 min=0.602 max=7.610 ms n=10
1000 publicar_geral mediana=0.271 min=0.198 max=6.011 ms n=10
1000 finalizacao mediana=0.438 min=0.231 max=3.986 ms n=10
1000 total mediana=2939.943 min=2741.069 max=3210.006 ms n=10
```

Na Etapa 3 a primeira importação sintética de 100 transações teve mediana de 157,267 ms. Nesta execução a mediana foi 309,286 ms: a nova medição acrescenta bloqueio, manifesto, sincronizações e releitura dos dois OFX. Os métodos e condições não são idênticos, portanto não é uma estimativa controlada de custo. A releitura e conversão do OFX domina a medição; a segurança não foi reduzida para atingir uma meta. O resultado não representa inicialização do executável Windows.
