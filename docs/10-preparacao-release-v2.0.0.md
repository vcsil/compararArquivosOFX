# Preparação da release v2.0.0

Status: **preparada para revisão, ainda não publicada**. Não executar merge, tag ou release sem aprovação explícita do mantenedor.

## Versão

- Produto: ComparaOFX 2.0
- Plataforma: Windows (console)
- Distribuição principal: Nuitka **onefile**, `ComparaOFX.exe`
- Ícone azul original adaptado, interface Colorama
- Executável **não assinado** (Authenticode `NotSigned`)

## Notas de versão sugeridas

### Novidades
- Interface colorida e menus de instituições descobertas automaticamente
- Organização de extratos por instituição, ano, mês, dia e número da importação
- Filtragem de transações novas por FITID, detecção de divergências e conflitos financeiros
- Geração do `OFX Limpo-DDMMAAAAHHMM.ofx` e atualização de `OFXGeral-AAAA-MM-DD.ofx`
- Preservação dos arquivos originais e anexos, proteção contra sobrescrita
- Manifestos e recuperação de operações interrompidas, com compatibilidade v1/v2
- Ícone azul, tratamento de mensagens de sucesso, avisos e erros

### Uso
1. Baixe o arquivo `ComparaOFX.exe` da release oficial e confira seu SHA-256 publicado nela.
2. Coloque o EXE numa pasta dedicada. Crie uma subpasta para cada instituição.
3. Coloque um OFX novo na pasta do EXE; execute e escolha a instituição.
4. Confira as saídas organizadas. Mantenha um backup dos extratos antes do primeiro uso.

### Segurança e limitações
- Executável sem assinatura digital de editor. Assinatura futura requer certificado Code Signing válido.
- Um candidato Nuitka anterior foi detectado como `Program:Win32/Contebrew.A!ml` no computador do usuário, sem diagnóstico conclusivo. Os últimos candidatos passaram em varreduras do Defender no runner e em testes manuais, mas isso não demonstra que a detecção anterior era falsa. Se o antivírus apresentar detecção, mantenha o arquivo em quarentena e investigue; não desative a proteção.
- Os testes usam dados sintéticos. A compatibilidade com todas as variantes bancárias OFX existentes não é garantida.

## Fonte e proveniência do binário homologado

- Branch: `codex/comparaofx-2.0-colorama`
- HEAD anterior à documentação de release: `1d25b1e7c03264d6996b34de5da64edad4173e3a`
- Código efetivamente usado no build final: `df7443e`, conforme o workflow `43512246781`
- Workflow: https://github.com/vcsil/compararArquivosOFX/actions/runs/43512246781
- Nuitka onefile homologado manualmente: `ComparaOFX.exe`
- SHA-256 desse EXE: `f90f2d7c6bcd183f2ed0f385dfbdb9eccc9286ddc295b14cb9ea4a080093de3f`
- Bytes: `8084992`
- 158 testes Linux e 158 Windows passaram, 7 falhas esperadas históricas e 4 ignorados no Linux.
- 6/6 jobs aprovados no workflow de referência.

**Cuidado com hashes:** a recompilação em outra execução, após o merge, pode gerar um binário diferente. Não copie automaticamente o hash acima para um EXE novo. Registre e publique o hash calculado a partir dos bytes exatos anexados à release.

## Procedimento de publicação controlada

1. Revisar o PR desta branch para `master`, incluindo todas as 46+ alterações de código, documentação, scripts e testes das Etapas 0–9. A versão antiga `dist/Compara OFX.exe` **não pode ser removida nem sobrescrita**.
2. Confirmar todos os checks no SHA mais recente do PR. Revisar branch protection, diferenças e ausência de mudanças não relacionadas.
3. Após aprovação expressa do mantenedor, fazer merge. Não forçar o merge nem desabilitar checks.
4. Após merge, executar o workflow em `master`, e selecionar o candidato Nuitka onefile gerado no próprio commit publicado. Se for preferível publicar o EXE homologado anteriormente, preservar a exata identidade do binário e declarar o commit de origem diferente do merge.
5. Conferir SHA-256 final, assinatura `NotSigned`, tamanho, ícone, inventário, smoke, resultados de antivírus e funcionamento manual. Não criar exceções no Defender.
6. Criar tag anotada `v2.0.0` no commit de `master` aprovado e GitHub Release com `ComparaOFX.exe` e arquivo `SHA256SUMS.txt` referente ao binário anexado. Incluir as notas acima e aviso de ausência de assinatura.
7. Confirmar que o download funciona, que o hash bate e que o executável legado continua intacto. Só então anunciar a release.

Os artifacts de workflow têm retenção limitada (7 dias). Uma GitHub Release precisa de anexos próprios para download persistente.

## O que não fazer

- Não anexar PDFs, OFX reais, logs contendo dados de conta ou arquivos temporários do usuário.
- Não publicar ZIP de toda a árvore do repositório como se fosse a distribuição onefile.
- Não usar a versão `master` anterior como se fosse 2.0.
- Não alterar o código financeiro durante a publicação.
