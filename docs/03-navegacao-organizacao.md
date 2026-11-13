# Navegação e organização — Etapa 3

Na execução empacotada, a raiz é a pasta real de `sys.executable`, nunca `_MEIPASS` nem o diretório de trabalho; para desenvolvimento e testes `main(raiz=...)` permite definir a raiz. A execução Python normal usa a raiz do repositório. Nenhuma lista de bancos é fixa: pastas imediatas não ocultas são listadas alfabeticamente, exceto diretórios técnicos conhecidos (`src`, `docs`, `tests`, `build`, `dist`, ambientes virtuais e outros enumerados em `organization.py`). O nome da pasta não comprova a conta. Links simbólicos e pontos de reparse são recusados.

OFX regulares diretamente na raiz são encontrados sem distinguir maiúsculas na extensão; temporários, atalhos e pastas não são selecionados. Um arquivo é selecionado automaticamente; com mais de um, há seleção numérica e cancelamento. Outros OFX ficam na raiz. Anexos elegíveis são PDF, PNG, JPG/JPEG, TIF/TIFF, CSV, XLSX e DOCX. Com um OFX são associados automaticamente e listados; com mais de um, o usuário seleciona números, todos, nenhum ou cancela. Scripts, executáveis, configurações e arquivos de outros tipos não são movidos. Os nomes originais são preservados e colisões não são sobrescritas.

Exemplo com dados sintéticos:

```text
Banco do Brasil/2026/11 - Nov 2026/2026-11-12/
├── OFXGeral-2026-11-12.ofx
├── 001/Extrato.ofx
├── 001/Comprovante.pdf
├── 001/OFX Limpo.ofx
└── 002/OFX Limpo.ofx
```

Ano, mês e dia usam a data local do processamento. O próximo número é o maior diretório numérico de três dígitos mais um; lacunas não são reutilizadas e o limite é 999. Históricos são localizados apenas na instituição selecionada, por ano/mês/dia e nome oficial exato, em ordem cronológica. O Geral do dia tem prioridade; caso contrário, usa-se o último anterior. Datas futuras com evidências, pastas inconsistentes, links e evidências sem Geral bloqueiam. Não há fallback para um histórico anterior quando a conta do mais recente não confere. A procura não interpreta todos os arquivos; apenas o selecionado é lido. Por segurança, diretórios inesperados dentro da instituição são rejeitados; organize históricos antigos fora da estrutura oficial separadamente antes de usar este fluxo.

Sem qualquer evidência histórica, `analisar(atual, None)` valida e preserva todas as transações na primeira importação. O motor bloqueia conflitos antes de criar saídas ou movimentar originais. Sem novidades, cria-se Limpo vazio válido e arquiva-se o original; o Geral do mesmo dia não é alterado. Se o Geral anterior pertence a outro dia, é copiado como referência do novo dia para manter rastreabilidade. Na ambiguidade de encoding tanto do atual quanto do histórico, o terminal solicita UTF-8, CP1252 ou cancelamento; não persiste a escolha. `COMPARAOFX_DEBUG=1` exibe traceback para diagnóstico e pode incluir dados do arquivo; mantenha-o desativado no uso comum.

O plano verifica nomes, permissões aproximadas, hashes de entrada e histórico, prepara os modelos em memória e só prossegue com resultado aprovado. Depois cria o Limpo, copia cada original e anexo com criação exclusiva, verifica hashes, grava o Geral e só então remove arquivos da raiz. Alterações intermediárias podem deixar cópias e saídas parciais; a atualização do Geral é direta e uma falha de gravação pode corromper o histórico. Não há transação atômica, rollback ou controle de concorrência; verificações de permissões e hashes não impedem corridas. **Não usar em produção com dados financeiros reais antes da Etapa 4.**

Testes: `venv/bin/python -m unittest discover -s tests -v`. Benchmark sintético: `PYTHONPATH=src venv/bin/python tests/benchmark_etapa3.py`. Nenhum extrato real está incluído.

## Desempenho observado

Linux x86-64, Python 3.12.14, dez repetições; mediana, mínimo e máximo abaixo. O primeiro menu inclui início do processo Python e não inclui resposta do usuário. Fluxo mede primeira importação de 100 transações sintéticas, sem espera, e inclui parse, gravação e cópia; cache e I/O não são controlados. Não é medição do executável Windows.

```text
Linux-6.18.57-x86_64-with-glibc2.41 3.12.14
instituições: mediana=0.010 min=0.009 max=0.044 ms n=10
extratos: mediana=0.015 min=0.014 max=0.034 ms n=10
histórico com 20 dias: mediana=1.363 min=1.229 max=1.858 ms n=10
processo Python até primeiro menu: mediana=19.526 min=17.751 max=24.973 ms n=10
primeira importação 100 transações: mediana=157.267 min=153.049 max=161.662 ms n=10
```

Atualização da Etapa 4: a descrição de gravação direta acima é histórica; consulte `04-integridade-recuperacao.md` para o protocolo atual e suas limitações.
