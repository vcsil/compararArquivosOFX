# ComparaOFX 2.0

Aplicativo de console para Windows que **organiza extratos OFX por instituição e data** e identifica movimentações novas sem duplicar transações já importadas.

A versão 2.0 mantém a interface colorida com Colorama, usa um ícone azul e acrescenta verificações de identidade financeira, recuperação de operações interrompidas e proteção dos arquivos originais.

## Download e segurança

A distribuição principal é **ComparaOFX.exe — Nuitka onefile**. Consulte a [página de Releases](https://github.com/vcsil/compararArquivosOFX/releases) para obter a versão oficial, notas, SHA-256 e limitações. **Não confunda os artifacts temporários de teste com uma release oficial.**

**Importante:** esta versão não possui assinatura digital Authenticode. Houve uma detecção anterior do Microsoft Defender em um *candidato diferente*, sem diagnóstico conclusivo. Se o antivírus detectar uma ameaça, não a permita e não desative a proteção. Os testes automatizados e a homologação manual não são garantia de ausência de malware.

O aplicativo executa localmente, sem precisar instalar Python. Ele move o OFX original para a estrutura organizada **somente após** o processamento e as verificações necessárias. Faça backup dos extratos antes do primeiro uso.

## Como usar

1. Crie uma pasta dedicada para o ComparaOFX e coloque `ComparaOFX.exe` dentro dela.
2. Crie uma subpasta para cada instituição financeira, por exemplo `Banco A` e `Banco B`. O programa descobre essas pastas automaticamente.
3. Copie o extrato novo (arquivo `.ofx`) para a **mesma pasta do executável**. Anexos como PDFs e imagens também podem ser colocados ali.
4. Abra `ComparaOFX.exe`, selecione a instituição e acompanhe o relatório de créditos, débitos, duplicatas e novas movimentações.
5. Confira os arquivos organizados na subpasta da instituição. Não modifique manualmente arquivos temporários de recuperação.

### Exemplo de estrutura

```text
Meus Extratos/
├── ComparaOFX.exe
├── Entrada.ofx
├── Banco A/
└── Banco B/
```

Após importar `Entrada.ofx` para `Banco A`, o programa cria uma estrutura do tipo:

```text
Meus Extratos/
├── ComparaOFX.exe
├── Banco A/
│   └── 2026/
│       └── 11 - Nov 2026/
│           └── 2026-11-13/
│               ├── OFXGeral-2026-11-13.ofx
│               └── 001/
│                   ├── Entrada.ofx
│                   └── OFX Limpo-131120261830.ofx
└── Banco B/
```

Os nomes e horários ilustram a convenção de organização, não dados bancários reais. O arquivo `OFX Limpo` contém as novas movimentações e `OFXGeral` mantém o histórico consolidado do dia. A versão 2.0 compara principalmente o `FITID` para evitar duplicações e bloqueia conflitos financeiros.

## Observações de uso

- Instituições diferentes devem ter subpastas próprias; não misture contas e históricos.
- Reimportar um extrato já processado não deve duplicar movimentações no Geral.
- Se houver dados inconsistentes, uma operação interrompida ou identificação ambígua de codificação, siga os avisos do terminal; não force a gravação.
- Para desativar cores no terminal, defina a variável de ambiente `NO_COLOR`.
- O programa prioriza a integridade dos dados sobre a velocidade: pode levar mais tempo com milhares de transações.

## Desenvolvimento e testes

Requisitos para executar a partir do código: Python 3.12 e as dependências de `requirements.txt`.

```bash
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python src/comparaArqOFX.py
```

A compilação do EXE Windows utiliza `scripts/build_windows.ps1` e Nuitka; a auditoria de empacotamento verifica que módulos de testes não sejam distribuídos no executável. Não faça build sobre a pasta `dist/` do legado.

Documentação detalhada: [organização](docs/03-navegacao-organizacao.md), [integridade e recuperação](docs/04-integridade-recuperacao.md), [validação final](docs/06-validacao-final.md), [auditoria de empacotamento](docs/08-otimizacao-segura.md), [interface Colorama](docs/09-interface-colorama.md) e [segurança e assinatura](docs/07-icone-assinatura-seguranca.md).

O executável da versão antiga permanece preservado em `dist/Compara OFX.exe` para fins históricos; **não é o executável de distribuição da versão 2.0**.
