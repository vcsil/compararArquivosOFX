# Otimização segura do ComparaOFX 2.0

## Decisão e escopo

A candidata restaura a estratégia da Etapa 6 para saídas equivalentes. O código de produção em `src/` e `requirements.txt` é idêntico ao de `fc9479e` (`git diff fc9479e HEAD -- src requirements.txt`); não se afirma um ganho frente à Etapa 6. O commit `f83dc16` fazia uma segunda leitura semântica, inclusive para saídas equivalentes. Neste caso, o Limpo já foi integralmente interpretado e validado, os bytes esperados são iguais, as assinaturas financeiras coincidem e o hash de cada arquivo efetivamente gravado é conferido. O Geral diferente continua sendo relido. A suíte inclui corrupção do Geral temporário idêntico e a exigência de releitura quando diferente.

## Cópias do modelo

O experimento reproduzível é `PYTHONPATH=src venv/bin/python scripts/benchmark_copy_experiment.py --repeticoes 2`. Um `deepcopy` da raiz `ofxtools.models.ofx.OFX` falha em `KeyError: 'status'`; `copy.copy` também falha, com `KeyError: 'signonmsgsrqv1'`. O mecanismo relevante do traceback é:

```text
copy._reconstruct -> hasattr(y, '__setstate__')
ofxtools.models.base.Aggregate.__getattr__ -> getattr(self, subaggregate)
ofxtools.Types.SubAggregate.__get__ -> obj.__dict__[self.name]
KeyError: 'status'
```

O objeto que dispara a exceção é `ofxtools.models.signon.SONRS`: a instância recém-alocada pela reconstrução ainda não tem o subagregado `status` no `__dict__`; a consulta de protocolo de cópia aciona `__getattr__` e o descritor antes da inicialização. Isso não significa que falte `status` no modelo original válido. Não se encontrou protocolo de cópia próprio que evite esse percurso nos agregados examinados.

O protótipo estrutural cria agregados, listas e dicionários independentes, mas depende de detalhes internos do ofxtools e usa `deepcopy` para outros tipos. Comparou bytes e assinaturas contra a serialização/reparse, inclusive com histórico e saída vazia, e verificou mutações em lista, transações, FITID, MEMO, valor, datas, conta, período e saldo. Existe um contraexemplo: um `tzinfo` mutável criado programaticamente cuja implementação de `__deepcopy__` retorna o próprio objeto é aceito na análise; a alteração do fuso na cópia altera o modelo original. O reparse mantém a independência. O leitor normal produz fusos imutáveis; o contraexemplo não afirma que um arquivo OFX comum produz esse objeto. Uma estratégia futura poderia restringir ou reconstruir explicitamente os tipos e recorrer ao reparse quando necessário, mas isso precisa de prova de equivalência e cobertura mais ampla. O protótipo não é usado em produção.

Microbenchmark sintético, duas repetições com `tracemalloc` ativo, metade das transações selecionada; memória = pico de alocações Python adicionais, não RSS. A instrumentação aumenta os tempos. Não extrapolar esses valores para o fluxo completo:

| Transações | Serialização/reparse: mediana s / pico bytes | Protótipo: mediana s / pico bytes |
|---:|---:|---:|
| 100 | 0,4350 / 544.500 | 0,0023 / 61.632 |
| 1.000 | 4,0547 / 5.069.278 | 0,0205 / 585.544 |
| 10.000 | 43,1855 / 49.930.512 | 0,2298 / 5.612.296 |

## Medições do fluxo

Em Linux, Python 3.12.14, na mesma máquina, dados sintéticos, duas repetições e mediana; medições sequenciais sem isolamento de carga ou controle de cache. Etapa 6 e candidata têm fonte de produção idêntica, portanto a primeira linha também representa a candidata, sem uma terceira medição independente. O pico é medido em uma execução separada com `tracemalloc`, apenas alocações Python durante o fluxo; não inclui a geração da entrada e não é RSS. A etapa de filtragem inclui serialização; as colunas podem se sobrepor. Escrita/publicação cobre as funções instrumentadas de armazenamento, não todas as cópias, flushes e fsyncs; estes estão no total.

| Estado | Transações | Leitura s | Análise s | Filtragem s | Serialização s | Leitura de validação s | Assinaturas s | Escrita/publicação s | Total s | Pico bytes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Etapa 6 / candidata | 100 | 0,0669 | 0,00026 | 0,0744 | 0,0180 | 0,0626 | 0,00027 | 0,0069 | 0,2281 | 1.280.379 |
| Etapa 6 / candidata | 1.000 | 0,6502 | 0,00190 | 0,6737 | 0,1631 | 0,5947 | 0,00220 | 0,0070 | 2,0226 | 5.892.677 |
| Etapa 6 / candidata | 10.000 | 6,9186 | 0,01909 | 7,4802 | 1,7711 | 6,1718 | 0,02779 | 0,0149 | 21,5426 | 57.925.592 |
| f83dc16 | 100 | 0,0685 | 0,00024 | 0,0791 | 0,0189 | 0,1353 | 0,00047 | 0,0078 | 0,3094 | 1.309.468 |
| f83dc16 | 1.000 | 0,6889 | 0,00180 | 0,7305 | 0,1663 | 1,2698 | 0,00317 | 0,0086 | 2,7983 | 6.248.865 |
| f83dc16 | 10.000 | 6,9189 | 0,01813 | 7,5783 | 1,7891 | 13,3827 | 0,04091 | 0,0174 | 28,9431 | 63.325.685 |

Em 10.000 transações, a diferença observada entre medianas foi 7,40 s, sem atribuir precisão estatística a apenas duas repetições. O teste cobre um caso de Limpo e Geral equivalentes; outros históricos podem exigir leitura independente. Comandos: `PYTHONPATH=src venv/bin/python scripts/benchmark_full_workflow.py --repeticoes 2 --memoria`; para comparar revisões, executar com fontes e fixtures da respectiva revisão, no mesmo ambiente.

## Legado

`controller.ofx_functions` preserva `carregar_ofx()` e as funções históricas `pegar_dia_insterseccao`, `pegar_infos_transacoes`, `remove_transacao`, `remove_anteriores`, `salvar_ofx`, `salvar_ofx_geral` e `junta_transacoes`. O PyInstaller incorpora o módulo inteiro; no relatório de compilação Nuitka a inclusão do módulo não prova que cada função permaneça no código final. Os testes impedem chamadas legadas no fluxo moderno e preservam sete falhas históricas esperadas. Separar o legado em módulo próprio, com compatibilidade e testes históricos mantidos, é uma proposta futura: imports estáticos de compatibilidade ainda poderiam empacotá-lo e uma mudança extensa neste momento aumentaria o risco.

## Execução inicial de f83dc16

[Workflow 43450529195](https://github.com/vcsil/compararArquivosOFX/actions/runs/43450529195): testes, PyInstaller, Nuitka e comparação concluídos com sucesso. PyInstaller onefile: 9.807.803 bytes, SHA-256 `716c2c2206de5864102067bfc2a249d451c95433cd7dd330e3cb4af98260b811`. Nuitka onefile: 8.003.584 bytes, `aea12b120486da73787e398e87c23d34a72fb47a130c9de6b77db1949874a5c8`. Nuitka standalone: executável de 12.162.560 bytes, `b891571b5421b961e60986fe33ce01cf94c8a996afddde39688630368fa589bc`; distribuição de 22 arquivos, 27.968.360 bytes. Esses hashes pertencem a f83dc16, não aos builds finais. Defender não indicou detecção associada nessa execução; o alerta anterior `Program:Win32/Contebrew.A!ml` continua sem diagnóstico conclusivo e uma varredura limpa não comprova ausência de malware.

## Recuperação medida

O teste força interrupção após publicação e mede apenas `recuperar_concluida`, incluindo as verificações executadas nessa recuperação; a preparação e a importação interrompida ficam fora do cronômetro. Duas repetições, mesma máquina Linux, medianas: 100 transações 0,00218 s; 1.000 transações 0,00321 s; 10.000 transações 0,01021 s. `safe_storage.py` é idêntico entre a Etapa 6, f83dc16 e a candidata; a medição foi feita na Etapa 6, não repetida em cada revisão. Comando: `PYTHONPATH=src venv/bin/python scripts/benchmark_full_workflow.py --somente-recuperacao --repeticoes 2`.

## Inventário real dos builds Windows

Os inventários completos da execução do commit `827a590` foram extraídos das anotações do próprio workflow, descompactados e conferidos pelo SHA-256 publicado. Consulte [PyInstaller onefile](inventarios/pyinstaller-onefile-windows.json), [Nuitka standalone](inventarios/nuitka-standalone-windows.json) e [Nuitka onefile](inventarios/nuitka-onefile-windows.json). O primeiro examina o TOC externo, o PYZ e `base_library.zip` do executável; os outros usam o relatório de compilação de cada build. Para standalone também foram enumerados os 22 arquivos físicos e inspecionados eventuais ZIPs. Os relatórios do Nuitka descrevem módulos analisados/compilados; não equivalem à descompilação de cada função do executável.

| Conteúdo examinado | PyInstaller onefile | Nuitka standalone | Nuitka onefile |
|---|---:|---:|---:|
| Módulos listados | 229 | 451 | 451 |
| Testes ou ferramentas próprios encontrados | 0 | 0 | 0 |
| `unittest`, `pytest`, `PIL`, `pefile` ou `test_baseline` | não | não | não |
| `controller.ofx_functions` e `ofxtools.Client` | sim | sim | sim |

Esses resultados descrevem os artefatos, não o conteúdo do repositório ou do ambiente: o build instala Pillow e pefile para verificar o ícone, mas eles não aparecem nos inventários das aplicações. `ofxtools/__init__.py` importa `OFXClient` de `ofxtools.Client`; excluí-lo cegamente pode quebrar o import. O pacote também contém vários módulos de modelo `ofxtools`; sua eliminação requer análise de dependências e teste de compatibilidade, não demonstrada aqui. Não se afirma minimalidade absoluta. A verificação CI recusa testes e scripts próprios incluídos por nome ou como origem renomeada no relatório Nuitka; no standalone verifica também arquivos físicos e ZIPs.

## Builds Windows finais

[Workflow 43455514175](https://github.com/vcsil/compararArquivosOFX/actions/runs/43455514175), commit de build `827a5900804c109db560412755caf43ee8af71b8`. As suítes Linux e Windows e os três builds passaram; os scripts conferem recurso PE do ícone azul, assinatura ausente esperada e smoke financeiro com recuperação v1/v2, nomes, Geral, originais, conflito e interrupção. Candidatos são **não assinados**, sem certificado Code Signing configurado.

| Artefato | Bytes do executável | SHA-256 |
|---|---:|---|
| PyInstaller onefile | 9.807.873 | `d60fe66aeb90e06246669d3590c95172ef74b3a29db4ab4add052ac0502f49e4` |
| Nuitka onefile | 8.005.120 | `7b233732802dff1c9e2cc7ba235e557971f7e414b1a9a5206f24b1a9bb7dc657` |
| Nuitka standalone | 12.163.072 | `26086024a8663b03f6f0870187480d3fc53b9e6ca85e4f7f227deed907a03df4` |

O standalone completo tem 22 arquivos e 27.968.872 bytes. Nas três varreduras, Defender não registrou detecção associada, usando assinatura `1.463.283.0`, atualizada em 2026-11-13 10:47:57 UTC. Uma tentativa de atualização de assinaturas gerou aviso de falha; portanto não se pode afirmar que a assinatura mais recente foi utilizada. Não houve exclusões. O alerta anterior `Program:Win32/Contebrew.A!ml` permanece sem diagnóstico conclusivo; ausência de detecção nesta varredura não prova ausência de malware. Os artefatos e relatórios do CI têm retenção configurada de sete dias.

Todos os jobs terminaram com sucesso, inclusive a comparação no mesmo runner. Nela foram usados Windows, Python 3.12.10 e AMD EPYC 7763; os resultados são da mesma máquina, sem comparar CPUs diferentes. Medianas de inicialização após 15 execuções aquecidas e de processamento para 100/1.000 transações com três repetições; para 10.000 houve apenas uma execução, sem mediana estatística confiável:

| Candidato | Inicialização aquecida ms | 100 transações ms | 1.000 transações ms | 10.000 transações ms, n=1 |
|---|---:|---:|---:|---:|
| PyInstaller onefile | 514,055 | 1.410,907 | 4.872,065 | 37.109,315 |
| Nuitka standalone | 57,816 | 824,057 | 4.248,482 | 39.030,387 |
| Nuitka onefile | 393,734 | 1.097,004 | 4.590,679 | 41.573,776 |

São medições sintéticas, sujeitas a variação de runner e cache; não demonstram ganho da cópia estrutural, que não foi implantada. Não houve merge em master nem release.
