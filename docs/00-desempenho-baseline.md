# Desempenho de referência

Ambiente Linux x86-64, Python 3.12.14. O executável Windows PE32+ tem 7.711.392 bytes e contém mensagens PyInstaller; a configuração de build e o modo onefile não foram identificados. Não é possível medir inicialização do executável Windows neste ambiente. Uma execução de `python -X importtime -c 'import colorama, ofxtools.Parser'` registrou 98,458 ms acumulados para `ofxtools.Parser`; é uma única observação, não mediana nem medida do executável. Comparação em 100/1.000/10.000 transações, leitura e serialização ainda não foram cronometradas.

A comparação aninhada e remoção em listas sugerem custo quadrático; isso é análise de código, não benchmark. Para etapa 5 medir no Windows real, com múltiplas execuções e mediana/faixa, separando arranque de processamento. Avaliar importação tardia, Counter para multiplicidades, estruturas indexadas, scandir e pathlib, e comparar PyInstaller e Nuitka por medições; nenhuma ferramenta tem garantia de abertura abaixo de um segundo.

## Medições da missão 0.1

`venv/bin/python tests/benchmark_baseline.py`: Linux 6.18.57 x86-64, glibc 2.41, Python 3.12.14, AMD EPYC 9V74, 5 CPUs visíveis. Dez repetições por cenário; mediana, mínimo e máximo em milissegundos:

| Cenário | Mediana | Mínimo | Máximo |
|---|---:|---:|---:|
| Processo Python novo + importação ofxtools.Parser | 99,487 | 92,344 | 146,328 |
| Parse e conversão SGML, 1.000 | 701,341 | 644,526 | 740,480 |
| Comparação, 100 | 0,284 | 0,242 | 0,590 |
| Comparação, 1.000 | 25,365 | 25,002 | 25,744 |
| Comparação, 10.000 | 2.712,563 | 2.630,827 | 2.873,848 |
| Serialização e escrita, 1.000 | 118,244 | 106,913 | 134,611 |

As entradas são geradas antes da medição. A comparação reproduz o laço de comparação por pares do script, sem correspondências (pior caso), sem parse, geração ou remoções; não mede processamento completo. A escrita inclui serialização e I/O local, não inclui parse. Importação usa processo novo e inclui inicialização do Python, com cache do SO não controlado; não representa arranque frio nem tempo do executável. As demais medições são no mesmo processo, sem controle de cache ou carga. A progressão observada é compatível com custo quadrático nesse cenário; outros perfis podem diferir.

O binário contém mensagens PyInstaller, mas onefile/onedir não foi confirmado. Onefile extrai arquivos antes de executar; onedir usa arquivos já extraídos. Inicialização do bootloader, extração, antivírus, disco e imports podem contribuir para atraso; não foram isolados aqui. Para medir Windows, em diretório temporário vazio execute `powershell -File tests/benchmark_windows.ps1 -Exe 'C:\caminho\Compara OFX.exe' -Runs 10`. O script mede início do processo até o primeiro caractere emitido no stdout redirecionado, não necessariamente visibilidade em console; buffering pode afetar resultado. Registre também medição manual até prompt visível, versão Windows, CPU, SSD e antivírus. Execute séries após reinício e aquecidas identificando condições, sem alegar cache frio sem controle. O script Windows não foi executado neste Linux.
