# Plano das próximas etapas

1. Leitura: investigar parser, codificações e XML/SGML em `controller/ofx_functions.py`; risco de corrupção silenciosa. Testar bytes sintéticos e amostras locais autorizadas; concluir com preservação de campos e original.
2. Deduplicação e conferências: depende da leitura; afeta script principal e funções OFX. Risco de colisões e contas distintas. Testar multiplicidade, FITID, cronologia e ausência de histórico; concluir com invariantes e bloqueio de inconsistências.
3. Organização: depende de leitura e seleção; afeta navegação e diretórios. Risco de colisões e movimentação prematura. Testar seleção de múltiplos OFX, anexos e diretórios em sistemas temporários; concluir com organização após validação.
4. Integridade e recuperação: depende das etapas 1–3; afeta escrita e orquestração. Risco de falha parcial. Injetar falhas de escrita, renomeação e interrupções; concluir com histórico anterior recuperável e rastreabilidade.
5. Empacotamento: depende da aplicação estável; adicionar configuração de build. Risco de tempo de abertura e tamanho. Medir PyInstaller e alternativas em Windows; concluir com executável portátil validado e tempos registrados.
6. Validação e lançamento: depende das etapas anteriores; afeta testes e documentação. Risco de incompatibilidade bancária. Validar Windows, formatos, contas, volume e recuperação; concluir com evidências e checklist de lançamento.
