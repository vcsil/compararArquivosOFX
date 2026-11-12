# Testes de referência

Executar `venv/bin/python tests/fixtures/smoke_baseline.py`. O teste sintético executado verifica leitura SGML, interseção, remoção de dias anteriores e de FITID, gravação e releitura e união. Também confirma que caminhos construídos com barras invertidas não correspondem a caminhos Linux. Não altera extratos reais.

PASSOU: cenário funcional de operações isoladas com dados sintéticos. FALHA CONHECIDA: caminhos Windows impedem fluxo de arquivos normal em Linux. BLOQUEADO/não executado: executável Windows, extratos reais, XML, divergência de encoding, IDs repetidos, contas distintas, reprocessamento e ordem de diretórios. O script não substitui uma suíte completa de regressão; não há contagens por caso. O programa principal executa imediatamente na importação e exige isolamento adicional para testes completos.
