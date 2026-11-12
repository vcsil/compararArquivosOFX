# Testes de referência

Executar `venv/bin/python tests/fixtures/smoke_baseline.py`. O teste sintético executado verifica leitura SGML, interseção, remoção de dias anteriores e de FITID, gravação e releitura e união. Também confirma que caminhos construídos com barras invertidas não correspondem a caminhos Linux. Não altera extratos reais.

PASSOU: cenário funcional de operações isoladas com dados sintéticos. FALHA CONHECIDA: caminhos Windows impedem fluxo de arquivos normal em Linux. BLOQUEADO/não executado: executável Windows, extratos reais, XML, divergência de encoding, IDs repetidos, contas distintas, reprocessamento e ordem de diretórios. O script não substitui uma suíte completa de regressão; não há contagens por caso. O programa principal executa imediatamente na importação e exige isolamento adicional para testes completos.

## Resultados da missão 0.1

Comando: `venv/bin/python -m unittest discover -s tests -v`. Resultado: **18 executados, 11 aprovados, 7 falhas esperadas, 0 falhas inesperadas, 0 ignorados**. Os testes aprovados caracterizam comportamento atual, inclusive rejeições e limitações; não significam aprovação dos requisitos futuros. Os casos 14, 15, 17 e 18 usam simulações para isolar o código; a interface completa Windows não foi executada.

| Caso | Resultado | Evidência |
|---|---|---|
| 1 SGML | Passou | Parse válido |
| 2 XML v2 | Passou | Declaração produzida por ofxtools |
| 3 XML sem OFX v2 | Passou | Rejeição de corpo mínimo |
| 4 UTF-8 declarado 1252 | Passou | Exceção reproduzida; normalização e cp1252 verificados |
| 5 vazio | Passou | Função retorna None |
| 6 malformado | Passou | Exceção observada |
| 7 idênticas | Passou | Mesma chave de comparação |
| 8 IDs distintos, mesmo memo/valor | Falha esperada | Chaves coincidem |
| 9 mesmo FITID, memo diferente | Falha esperada | Chaves divergem |
| 10 mesmo FITID, valor diferente | Falha esperada | Chaves divergem |
| 11 sem última data | Passou | FileExistsError |
| 12 dias anteriores | Passou | Removidos em exemplo ordenado |
| 13 reprocessamento | Falha esperada | União direta duplica transação |
| 14 criar/atualizar geral | Passou | Chamadas simuladas e união verificadas |
| 15 histórico ausente | Passou | Falha de busca simulada |
| 16 contas distintas | Falha esperada | União não rejeita contas |
| 17 diretórios fora de ordem | Falha esperada | Índice depende da ordem fornecida |
| 18 falha de gravação | Falha esperada | Truncamento e erro simulados |

O fluxo completo de interface, escrita e navegação no Windows segue não executado; as amostras reais não estavam disponíveis. Os testes de identidade não executam o laço principal, cuja comparação usa apenas os pares extraídos. `expectedFailure` não corresponde a funcionalidade aprovada.
