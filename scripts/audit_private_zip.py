"""Auditoria LOCAL de ZIP privado. Nunca incluir o ZIP/saídas em Git ou no CI.

Somente extensões, contagens e códigos de resultado são emitidos. Nenhum EXE,
HTML ou anexo é executado. --codificacao é uma escolha explícita de cenário.
"""
import argparse
import collections
import contextlib
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import stat
import re
import sys
import tempfile
import warnings
import zipfile
from decimal import Decimal
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from controller.ofx_functions import carregar_ofx
from controller.ofx_io import OFXEncodingAmbiguaError
from controller.ofx_compat import OFXCompatError
from controller.organization import ANEXOS, OrganizacaoError
from controller.workflow import planejar, executar, _assinatura
from controller import safe_storage

BANCOS = ('Asaas', 'Bradesco CNPJ', 'Itau', 'Itau CNPJ', 'PagSeguro', 'Rede', 'Valori', 'Valori - Banking')


def extrair_seguro(arquivo, destino):
    with zipfile.ZipFile(arquivo) as z:
        entries = z.infolist()
        if len(entries) > 5000 or sum(e.file_size for e in entries) > 300 * 1024**2:
            raise ValueError('ZIP excede limites da auditoria')
        vistos = set()
        for e in entries:
            p = PurePosixPath(e.filename.replace('\\', '/'))
            mode = stat.S_IFMT(e.external_attr >> 16)
            if (p.is_absolute() or not p.parts or '..' in p.parts
                    or any(':' in x for x in p.parts) or e.flag_bits & 1
                    or mode not in (0, stat.S_IFREG, stat.S_IFDIR)
                    or p.as_posix().casefold() in vistos
                    or e.file_size > 50 * 1024**2
                    or (e.file_size > 1024**2 and e.file_size / max(1, e.compress_size) > 1000)):
                raise ValueError('ZIP inseguro ou incompatível')
            vistos.add(p.as_posix().casefold())
        # Validar CRC antes de criar qualquer arquivo.
        if z.testzip() is not None:
            raise ValueError('ZIP com CRC inválido')
        for e in entries:
            p = destino.joinpath(*PurePosixPath(e.filename.replace('\\', '/')).parts)
            if e.is_dir():
                p.mkdir(parents=True, exist_ok=True)
            else:
                p.parent.mkdir(parents=True, exist_ok=True)
                with p.open('xb') as out:
                    out.write(z.read(e))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def codigo(exc):
    if isinstance(exc, OFXEncodingAmbiguaError): return 'ESCOLHA_CODIFICACAO_NECESSARIA'
    if isinstance(exc, OFXCompatError): return 'OFX_INCOMPATIVEL_OU_DADO_AUSENTE'
    if isinstance(exc, OrganizacaoError):
        text = str(exc).casefold()
        if 'histórico legado' in text: return 'CONCILIACAO_LEGADA_NECESSARIA'
        if 'cronologia' in text or 'cobertura' in text or 'integralmente' in text: return 'CONTINUIDADE_NAO_COMPROVADA'
        if 'identidade' in text or 'conflito' in text: return 'CONFLITO_FINANCEIRO'
        return 'BLOQUEIO_SEGURO_ORGANIZACAO'
    return 'FALHA_' + type(exc).__name__


def conferir_financas_originais(path, modelo, codificacao):
    from controller.ofx_io import preparar_ofx
    from ofxtools.Parser import TreeBuilder
    from ofxtools.Types import DateTime
    try:
        formato, _, corpo = preparar_ofx(path.read_bytes())
    except OFXEncodingAmbiguaError:
        formato, _, corpo = preparar_ofx(path.read_bytes(), codificacao=codificacao)
    try:
        root = ET.fromstring(corpo)
    except ET.ParseError:
        builder = TreeBuilder(); builder.feed(corpo); root = builder.close()
    nodes = list(root.iter('STMTTRN'))
    txs = [t for s in modelo.statements for t in s.transactions]
    assert len(nodes) == len(txs)
    for node, tx in zip(nodes, txs):
        assert node.findtext('FITID') == tx.fitid
        assert Decimal(node.findtext('TRNAMT').replace(',', '.')) == tx.trnamt
        kind = node.findtext('TRNTYPE')
        assert {'IN':'CREDIT','OUT':'DEBIT'}.get(kind,kind) == tx.trntype
        stamp = node.findtext('DTPOSTED')
        assert DateTime().convert(stamp) == tx.dtposted
        assert stamp[:8] == tx.dtposted.strftime('%Y%m%d')
    accounts = list(root.iter('BANKACCTFROM'))
    assert len(accounts) == len(modelo.statements)
    stmts = list(root.iter('STMTRS'))
    assert len(stmts) == len(modelo.statements)
    for node, statement in zip(stmts, modelo.statements):
        assert Decimal(node.findtext('./LEDGERBAL/BALAMT').replace(',', '.')) == statement.ledgerbal.balamt
    for node, statement in zip(accounts, modelo.statements):
        for name in ('BANKID', 'BRANCHID', 'ACCTID', 'ACCTTYPE'):
            assert node.findtext(name) == getattr(statement.bankacctfrom, name.lower())


def auditar(arquivo, codificacao=None):
    original_hash = sha(arquivo)
    resultados = {}
    with tempfile.TemporaryDirectory(prefix='compara-private-') as temp:
        root = Path(temp); ref = root / 'reference'; ref.mkdir(mode=0o700)
        extrair_seguro(arquivo, ref)
        arquivos_hash = {p: sha(p) for p in ref.rglob('*') if p.is_file()}
        for nome in BANCOS:
            matches = [p for p in ref.rglob('*') if p.is_dir() and p.name == nome]
            if len(matches) != 1:
                resultados[nome] = {'resultado': 'INSTITUICAO_AUSENTE_OU_AMBIGUA'}; continue
            source = matches[0]; work = root / ('work-' + str(len(resultados))); work.mkdir()
            bank = work / nome; bank.mkdir()
            for p in source.iterdir():
                if p.is_dir(): shutil.copytree(p, bank / p.name)
                elif p.suffix.casefold() != '.exe': shutil.copyfile(p, work / p.name)
            historicos = {p: sha(p) for p in bank.rglob('*') if p.is_file()}
            def ler(p):
                try:
                    return carregar_ofx(p)
                except OFXEncodingAmbiguaError:
                    if codificacao is None:
                        raise
                    return carregar_ofx(p, codificacao=codificacao)
            erros = collections.Counter()
            for p in source.rglob('*'):
                if p.suffix.casefold() == '.ofx':
                    try:
                        modelo = ler(p)[1]
                        conferir_financas_originais(p, modelo, codificacao)
                        from controller.ofx_io import interpretar_ofx, serializar_ofx
                        assert _assinatura(modelo) == _assinatura(interpretar_ofx('xml', serializar_ofx(modelo)))
                    except Exception as exc: erros[codigo(exc)] += 1
            row = {'erros_leitura_roundtrip': dict(erros)}
            inputs = [p for p in work.iterdir() if p.is_file() and
                      (p.suffix.casefold() == '.ofx' or (nome.casefold() == 'rede' and p.suffix.casefold() == '.csv'))]
            if len(inputs) != 1:
                row['resultado'] = 'ENTRADA_NAO_SUPORTADA_OU_AMBIGUA'
            else:
                entrada = inputs[0]
                anexos = [p for p in work.iterdir() if p.is_file() and p != entrada and p.suffix.casefold() in ANEXOS]
                hashes = {p: sha(p) for p in (entrada, *anexos)}
                try:
                    plan = planejar(work, bank, entrada, anexos, leitor=ler)
                    from unittest.mock import patch
                    real = safe_storage.publicar_arquivo
                    def interromper(*args, **kwargs):
                        real(*args, **kwargs)
                        raise OSError('interrupção sintética privada')
                    with patch.object(safe_storage, 'publicar_arquivo', side_effect=interromper):
                        try: executar(plan)
                        except OSError: pass
                        else: raise AssertionError('Interrupção não ocorreu')
                    assert all(p.exists() and sha(p) == h for p,h in hashes.items())
                    with safe_storage.bloquear(bank): safe_storage.recuperar_concluida(bank)
                    assert not safe_storage.pendencias(bank)
                    for p,h in hashes.items():
                        assert not p.exists() and sha(plan.importacao / p.name) == h
                    assert all(p.exists() and sha(p) == h for p,h in historicos.items())
                    assert _assinatura(carregar_ofx(plan.geral)[1]) == plan.assinatura_geral
                    assert _assinatura(carregar_ofx(plan.importacao / plan.limpo_nome)[1]) == plan.assinatura_limpo
                    row.update(resultado='PUBLICADO_E_RECUPERADO', originais_e_anexos='HASH_IDENTICO', historicos='PRESERVADOS', saidas='RELIDAS_E_CONFERIDAS')
                except Exception as exc:
                    row['resultado'] = codigo(exc)
                    assert all(p.exists() and sha(p) == h for p,h in historicos.items())
                    row['historicos'] = 'PRESERVADOS'
            resultados[nome] = row
        assert all(p.exists() and sha(p) == h for p,h in arquivos_hash.items())
    assert sha(arquivo) == original_hash
    return {'codificacao_explicita': codificacao, 'zip_e_referencias': 'INALTERADOS', 'instituicoes': resultados}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('zip', type=Path)
    parser.add_argument('--codificacao', choices=('utf-8', 'cp1252'))
    parser.add_argument('--report', type=Path, required=True, help='Caminho privado FORA do checkout')
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    if args.report.resolve().is_relative_to(repo) or args.zip.resolve().is_relative_to(repo):
        parser.error('ZIP e relatório devem ficar fora do checkout')
    try:
        # Nem warnings nem exceções do parser podem divulgar valores privados.
        with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            warnings.simplefilter('ignore')
            result = auditar(args.zip, args.codificacao)
    except Exception as exc:
        print(json.dumps({'erro': codigo(exc)})); return 1
    args.report.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
