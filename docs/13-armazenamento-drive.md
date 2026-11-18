# Armazenamento e Google Drive — candidata de correção 2.1

## Causa e mudança

Base: master `cf004c7e746bdd75abd8b2b6a9c1fd07cfe7bd49`.
O legado gravava arquivos diretamente, sem a barreira por tipo de volume.
A proteção nova passou a exigir DRIVE_FIXED e NTFS/ReFS, a bloquear OneDrive
por variável de ambiente e a exigir st_nlink=1. A publicação de arquivo novo
usava os.link, operação que um provedor virtual pode não oferecer.

A correção conserva a máquina de estados e os manifestos v1/v2. No Windows:

- testa operações reais em subpasta descartável da instituição antes de processar;
- usa mutex Global do kernel, sem depender de byte-range locks msvcrt no Drive;
- publica arquivos completos por os.rename, sem substituir destinos existentes;
- permite st_nlink=0 somente se GetVolumeInformationW declarar ausência de suporte
  a hardlinks (FILE_SUPPORTS_HARD_LINKS). Se esse suporte existe ou não pode ser
  consultado, recusa a operação com diagnóstico específico;
- permite tags IO_REPARSE_TAG_CLOUD e variantes conhecidas, sem permitir junction,
  symlink ou tag desconhecida. Arquivos offline continuam sujeitos à releitura/hash.

No Windows, os.rename recusa destino existente. No mesmo volume, usa a primitiva
nativa de renomeação; não habilita cópia entre volumes. Não há fallback que escreva
bytes progressivamente no nome definitivo do Geral. os.replace fica reservado
à substituição já autorizada pelo fluxo e à atualização de manifestos.
Referências: [Python os.rename](https://docs.python.org/3.12/library/os.html#os.rename),
[MoveFileExW](https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-movefileexw),
[flags de volume](https://learn.microsoft.com/en-us/windows/win32/api/fileapi/nf-fileapi-getvolumeinformationw).

## Homologação em Windows com Drive real

Use um checkout da branch de correção e Python 3.12. Não é necessário fornecer
extratos, credenciais bancárias ou dados privados. Em PowerShell na raiz do checkout:

```powershell
py -3.12 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe scripts/probe_storage.py "G:\Minha unidade\Teste ComparaOFX"
```

Crie a pasta de teste antes. Repita para uma pasta NTFS local, uma pasta espelhada,
streaming e arquivos marcados como disponíveis offline. Aguarde o Drive concluir
cada sincronização; não rode o programa em outra máquina durante o teste.
O diagnóstico cria e remove somente sua própria subpasta temporária. Capture a saída:

```powershell
.\venv\Scripts\python.exe scripts/probe_storage.py "G:\Minha unidade\Teste ComparaOFX" *> drive-diagnostico.txt
$LASTEXITCODE
```

Sucesso exige código 0, `primitivas: PASS`, `suite_sintetica: PASS` e nenhum teste
com falha inesperada. A suíte selecionada verifica dois processos, morte do dono
do lock, interrupções antes/depois da publicação, recuperação v1/v2, reimportação,
hashes, destinos ocupados e ataques por links quando o volume permite criá-los.
Testes de symlink/junction podem ser ignorados por falta de permissão ou suporte;
esses itens ignorados não equivalem a homologação. Não ignore erro de integridade
nem remova manifestos para fazer a importação passar. A suíte completa é:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os builds candidatos são produzidos pelo workflow Windows existente, com smoke de
arquivos e recuperação, auditoria de empacotamento e SHA-256. Também podem ser feitos
com `scripts/build_windows.ps1 -Tool pyinstaller` e `-Tool nuitka` no Windows.
Não use dist/ legado como destino. Esses artefatos são candidatos, não releases.

## Limites das garantias

O mutex global previne duas instâncias com o mesmo caminho canônico da instituição
na mesma máquina, inclusive entre sessões; nomes 8.3 e capitalização são normalizados.
Mapeamentos diferentes da mesma pasta (por exemplo duas letras de unidade apontando
para o mesmo remoto) não são um protocolo de identidade distribuída: use um único
caminho e uma única máquina. Mutex abandonado é readquirido e a recuperação existente
inspeciona as pendências antes de nova importação.

Não existe lock entre computadores. SHA-256 continua sendo conferido após cópias,
antes de publicar e antes de remover cada original, inclusive na recuperação.
Isso detecta alterações externas observadas, mas não torna uma sequência de vários
arquivos uma transação remota nem impede alteração entre hash e rename/unlink.

Os testes observam o comportamento do provedor naquele momento. Não provam
atomicidade interna de um provedor proprietário nem durabilidade após queda de
energia/rede. Flush pode falhar e deve bloquear. No Windows não há fsync de diretório.
Uma falha ambígua deixa manifesto para inspeção; não se presume sucesso.

## Evidência desta implementação

Linux: suíte completa e diagnóstico sintético executados; resultados registrados no
relatório da alteração. Windows NTFS/ReFS, Drive espelhado, streaming e offline:
**pendentes de execução nativa**. Não foi montado Google Drive neste ambiente.
Não extrapole testes com mocks de metadados para uma homologação de volume real.
