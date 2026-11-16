"""Regressões sintéticas da auditoria 2.1; nenhum anexo financeiro real."""
import csv
import io
import json
import sys
import tempfile
import unittest
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from test_rede_csv import COLUNAS, linha, csv as dados, transacoes
from controller.rede_csv import carregar_csv_rede
from controller.ofx_functions import carregar_ofx
from controller.ofx_io import serializar_ofx, interpretar_ofx
from controller.workflow import planejar, executar, _assinatura
from controller.organization import OrganizacaoError, anexos, extrato_permitido
from controller import safe_storage as ss

FIXTURES = Path(__file__).parent / 'fixtures'

class AuditoriaRede(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.bank = self.root/'Rede'; self.bank.mkdir()
        self.day = date(2026,11,16)
    def source(self, *rows):
        p=self.root/'vendas.csv'; p.write_bytes(dados(*rows)); return p
    def import_rows(self,*rows,day=None):
        p=planejar(self.root,self.bank,self.source(*rows),hoje=day or self.day)
        executar(p); return p
    def test_notebook_golden_roundtrip(self):
        old=carregar_ofx(FIXTURES/'rede_notebook.ofx')[1]
        new=carregar_csv_rede(FIXTURES/'rede_sintetico.csv')[1]
        def fields(m):
            return [(t.fitid,t.dtposted,t.trnamt,t.trntype,t.name,t.memo) for t in transacoes(m)]
        self.assertEqual(fields(old),fields(new))
        self.assertEqual(fields(new),fields(interpretar_ofx('xml',serializar_ofx(new))))
        self.assertEqual(sum(t.trnamt for t in transacoes(new)),Decimal('30.75'))
        self.assertEqual(len(transacoes(new)),2)
        self.assertEqual(transacoes(new)[0].name,'M012 - Maquininha')
        self.assertEqual(transacoes(new)[0].memo,'Visa - Crédito - À vista Pre-Auto - 1x')
    def test_legacy_history_then_csv(self):
        old=self.root/'old.ofx';old.write_bytes((FIXTURES/'rede_notebook.ofx').read_bytes())
        p=planejar(self.root,self.bank,old,hoje=self.day);executar(p)
        src=self.root/'vendas.csv';src.write_bytes((FIXTURES/'rede_sintetico.csv').read_bytes())
        p=planejar(self.root,self.bank,src,hoje=self.day)
        self.assertEqual(p.resultado.relatorio.estado,'SEM_NOVIDADES'); executar(p)
    def test_partial_overlap_new_lots_and_next_day(self):
        p=self.import_rows(linha('A'),linha('B',hora='11:00'))
        first=p.geral.read_bytes()
        p=self.import_rows(linha('B',hora='11:00'),linha('C',hora='12:00'))
        self.assertEqual(p.resultado.relatorio.novas.quantidade,1)
        p=self.import_rows(linha('D',data='13/11/2026'),day=self.day+timedelta(days=1))
        self.assertEqual(len(transacoes(carregar_ofx(p.geral)[1])),4)
        self.assertEqual(transacoes(carregar_ofx(p.geral)[1])[0].fitid,'A - 10:30:01')
        self.assertEqual(len(transacoes(carregar_ofx(p.historico)[1])),3)
        # Snapshot anterior permanece intacto ao importar em outro dia.
        prior=p.historico.read_bytes()
        self.import_rows(linha('E',data='14/11/2026'),day=self.day+timedelta(days=2))
        self.assertEqual(p.historico.read_bytes(),prior)
    def test_reimport_and_all_new_same_day(self):
        self.import_rows(linha('A'))
        p=self.import_rows(linha('A'))
        self.assertEqual(p.resultado.relatorio.estado,'SEM_NOVIDADES')
        p=self.import_rows(linha('B'))
        self.assertEqual(len(transacoes(carregar_ofx(p.geral)[1])),2)
    def test_conflict_date_collision_and_backdated_block(self):
        p=self.import_rows(linha('A',data='13/11/2026'))
        before=p.geral.read_bytes()
        for row in (linha('A',data='13/11/2026',valor='1,00'),linha('A',data='14/11/2026'),linha('B')):
            with self.subTest(row=row):
                src=self.source(row);raw=src.read_bytes()
                with self.assertRaises(OrganizacaoError):planejar(self.root,self.bank,src,hoje=self.day)
                self.assertEqual(src.read_bytes(),raw);self.assertEqual(p.geral.read_bytes(),before)
    def test_out_of_order_preserved(self):
        p=self.import_rows(linha('B',data='13/11/2026'),linha('A'))
        self.assertEqual([t.fitid for t in transacoes(carregar_ofx(p.geral)[1])],['A - 10:30:01','B - 10:30:01'])
    def test_delimiters_encodings_quotes_reordered_columns(self):
        for delimiter in (';',',','\t'):
            for encoding in ('utf-8','utf-8-sig','cp1252'):
                with self.subTest(delimiter=delimiter,encoding=encoding):
                    cols=COLUNAS.split(';')[::-1]; values=linha('A',memo='Visa; "Especial"\nAção').split(';')
                    values=linha('A').split(';');values[7]='Visa; "Especial"\nAção'
                    out=io.StringIO(newline='');w=csv.writer(out,delimiter=delimiter)
                    w.writerow(cols);w.writerow(values[::-1])
                    src=self.root/'vendas.csv';raw=out.getvalue().encode(encoding);src.write_bytes(raw)
                    model=carregar_csv_rede(src)[1]
                    self.assertIn('Especial',transacoes(model)[0].memo)
                    self.assertEqual(src.read_bytes(),raw)
    def test_invalid_inputs_preserved(self):
        cases=[b'',b'wrong\n',dados(linha('A')).rsplit(b';', 3)[0],dados(linha('A'),linha('A')),
               dados(linha('A',status='')),dados(linha('A',status='Negada')),
               dados(linha('A',data='31/02/2026')),dados(linha('A',hora='25:00')),
               dados(linha('A',valor='NaN')),dados(linha('A',valor='0,00')),
               dados(linha('A',valor='-1,00')),dados(linha('A',valor='1,001')),
               dados(linha('')),dados(linha('A')).replace(b';M012;',b';;'),
               dados(linha('A')).replace(b';Visa;',b';"Visa;')]
        for raw in cases:
            with self.subTest(raw=raw[:30]):
                src=self.root/'vendas.csv';src.write_bytes(raw)
                with self.assertRaises(ValueError):carregar_csv_rede(src)
                self.assertEqual(src.read_bytes(),raw)
    def test_large_report(self):
        for count in (500,3000):
            src=self.source(*(linha(str(i),valor='0,01') for i in range(count)))
            m=carregar_csv_rede(src)[1]
            self.assertEqual(len(transacoes(m)),count)
            self.assertEqual(m.statements[0].ledgerbal.balamt,Decimal(count)/100)
    def test_only_exact_rede_and_never_csv_attachment(self):
        src=self.source(linha('A'))
        for name in ('Rede','REDE','rede','Banco Rede','Rede Empresa 2','Itaú'):
            self.assertEqual(extrato_permitido(name,src),name.casefold()=='rede')
        self.assertNotIn(src,anexos(self.root))
        other=self.root/'Outro';other.mkdir()
        original=self.root/'extrato.ofx';original.write_bytes((FIXTURES/'rede_notebook.ofx').read_bytes())
        with self.assertRaises(OrganizacaoError):planejar(self.root,other,original,[src])
    def identified(self,nsu,est='12345678'):
        src=self.source(linha(nsu));s=src.read_text(encoding='utf-8')
        rows=s.splitlines();rows[0]+=';número do estabelecimento';rows[1]+=';'+est
        src.write_text('\n'.join(rows)+'\n',encoding='utf-8');return src
    def test_establishment_binding_and_mixed_rejection(self):
        src=self.identified('A');p=planejar(self.root,self.bank,src,hoje=self.day);executar(p)
        self.assertEqual(carregar_ofx(p.geral)[1].statements[0].bankacctfrom.acctkey,'12345678')
        for src in (self.identified('B','87654321'),self.source(linha('B'))):
            with self.assertRaises(OrganizacaoError):planejar(self.root,self.bank,src,hoje=self.day)
        src=self.identified('A');s=src.read_text(encoding='utf-8');src.write_text(s+s.splitlines()[1].replace('12345678','87654321')+'\n', encoding='utf-8')
        with self.assertRaises(ValueError):carregar_csv_rede(src)
    def test_legacy_establishment_requires_explicit_binding(self):
        self.import_rows(linha('A'))
        src=self.identified('B')
        with self.assertRaises(OrganizacaoError):planejar(self.root,self.bank,src,hoje=self.day)
        (self.bank/'.rede.json').write_text(json.dumps({'estabelecimento':'12345678'}), encoding='utf-8')
        p=planejar(self.root,self.bank,src,hoje=self.day);executar(p)
        self.assertEqual(len(transacoes(carregar_ofx(p.geral)[1])),2)
    def test_recovery_each_publication_boundary(self):
        for boundary in ('iniciar','escrever','publicar_pasta','publicar_arquivo','unlink'):
            with self.subTest(boundary=boundary),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);bank=root/'Rede';bank.mkdir();src=root/'vendas.csv';raw=dados(linha('A'));src.write_bytes(raw)
                p=planejar(root,bank,src,hoje=self.day)
                injected = []
                if boundary=='unlink':
                    real=Path.unlink
                    def stop(path,*a,**kw):
                        if src.exists() and path.samefile(src):
                            injected.append('before removal')
                            raise OSError('injetada')
                        return real(path,*a,**kw)
                    ctx=patch.object(Path,'unlink',stop)
                else:
                    real=getattr(ss,boundary)
                    def stop(*a,_real=real,**kw):
                        result=_real(*a,**kw)
                        if boundary=='escrever' and not str(a[0]).endswith('.ofx'):
                            return result
                        raise OSError('injetada')
                    ctx=patch.object(ss,boundary,side_effect=stop)
                with ctx,self.assertRaises(OSError):executar(p)
                self.assertEqual(src.read_bytes(),raw)
                if boundary=='unlink':
                    self.assertEqual(injected, ['before removal'])
                if boundary=='publicar_pasta':
                    with ss.bloquear(bank),self.assertRaises(OrganizacaoError):
                        ss.recuperar_concluida(bank)
                    self.assertEqual(src.read_bytes(),raw)
                    self.assertEqual((p.importacao/src.name).read_bytes(),raw)
                    self.assertTrue(ss.pendencias(bank))
                    continue
                with ss.bloquear(bank):ss.recuperar_concluida(bank)
                self.assertFalse(ss.pendencias(bank))
                if src.exists():
                    p=planejar(root,bank,src,hoje=self.day);executar(p)
                self.assertEqual((p.importacao/src.name).read_bytes(),raw)
    def test_signature_detects_name_and_establishment(self):
        model=carregar_csv_rede(FIXTURES/'rede_sintetico.csv')[1];before=_assinatura(model)
        transacoes(model)[0].name='Mudança';self.assertNotEqual(_assinatura(model),before)

    def test_old_daily_snapshots_are_consolidated_and_conflicts_found(self):
        from controller.organization import pasta_dia
        from controller.rede_csv import consolidar_historicos
        for offset, row in enumerate((linha('A',data='12/11/2026'),linha('B',data='13/11/2026'))):
            folder=pasta_dia(self.bank,self.day+timedelta(days=offset));folder.mkdir(parents=True)
            day=self.day+timedelta(days=offset)
            model=carregar_csv_rede(self.source(row))[1]
            (folder/f'OFXGeral-{day.isoformat()}.ofx').write_bytes(serializar_ofx(model))
        p=self.import_rows(linha('C',data='14/11/2026'),day=self.day+timedelta(days=2))
        self.assertEqual(len(transacoes(carregar_ofx(p.geral)[1])),3)
        src=self.source(linha('A',data='15/11/2026'))
        with self.assertRaises(OrganizacaoError):planejar(self.root,self.bank,src,hoje=self.day+timedelta(days=2))
    def test_recovery_csv_cannot_be_moved_to_other_bank(self):
        src=self.source(linha('A'));p=planejar(self.root,self.bank,src,hoje=self.day)
        real=ss.publicar_arquivo
        def stop(*args):
            real(*args);raise OSError('injetada')
        with patch.object(ss,'publicar_arquivo',side_effect=stop),self.assertRaises(OSError):executar(p)
        other=self.root/'Outro';self.bank.rename(other)
        with ss.bloquear(other),self.assertRaises(OrganizacaoError):ss.recuperar_concluida(other)
        self.assertEqual(src.read_bytes(),dados(linha('A')))
    def test_recovery_interrupted_after_csv_copy_and_removal(self):
        import shutil
        for moment in ('copy','removed','recovery'):
            with self.subTest(moment=moment),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);bank=root/'Rede';bank.mkdir();src=root/'vendas.csv';raw=dados(linha('A'));src.write_bytes(raw)
                p=planejar(root,bank,src,hoje=self.day)
                injected = []
                if moment=='copy':
                    real=shutil.copyfileobj
                    def stop(*a,**kw):real(*a,**kw);raise OSError('injetada')
                    ctx=patch.object(shutil,'copyfileobj',side_effect=stop)
                elif moment=='removed':
                    real=Path.unlink
                    def stop(path,*a,**kw):
                        original = src.exists() and path.samefile(src)
                        real(path,*a,**kw)
                        if original:
                            injected.append('after removal')
                            raise OSError('injetada')
                    ctx=patch.object(Path,'unlink',stop)
                else:
                    real=ss.publicar_arquivo
                    def stop(*a,**kw):real(*a,**kw);raise OSError('injetada')
                    ctx=patch.object(ss,'publicar_arquivo',side_effect=stop)
                with ctx,self.assertRaises(OSError):executar(p)
                if moment=='removed':
                    self.assertEqual(injected, ['after removal'])
                    self.assertFalse(src.exists())
                else:
                    self.assertEqual(src.read_bytes(), raw)
                if moment=='recovery':
                    with patch.object(Path,'unlink',side_effect=OSError('injetada')),ss.bloquear(bank),self.assertRaises(OrganizacaoError):
                        ss.recuperar_concluida(bank)
                    self.assertEqual(src.read_bytes(),raw)
                with ss.bloquear(bank):ss.recuperar_concluida(bank)
                if src.exists():p=planejar(root,bank,src,hoje=self.day);executar(p)
                self.assertEqual((p.importacao/src.name).read_bytes(),raw)

    def test_recovery_checks_additional_snapshot_hashes(self):
        self.import_rows(linha('A'))
        src=self.source(linha('B',data='13/11/2026'))
        p=planejar(self.root,self.bank,src,hoje=self.day+timedelta(days=1))
        real=ss.publicar_arquivo
        def stop(*a,**kw):real(*a,**kw);raise OSError('injetada')
        with patch.object(ss,'publicar_arquivo',side_effect=stop),self.assertRaises(OSError):executar(p)
        before=p.historico.read_bytes();p.historico.write_bytes(b'alterado')
        with ss.bloquear(self.bank),self.assertRaises(OrganizacaoError):ss.recuperar_concluida(self.bank)
        self.assertTrue(src.exists())
        p.historico.write_bytes(before)
        with ss.bloquear(self.bank):ss.recuperar_concluida(self.bank)
        self.assertFalse(src.exists())

    def test_manifest_references_use_posix_paths_and_original_hashes(self):
        import hashlib
        first = self.import_rows(linha('A'))
        snapshot = first.geral
        digest = hashlib.sha256(snapshot.read_bytes()).hexdigest()
        src = self.source(linha('B', data='13/11/2026'))
        plan = planejar(self.root, self.bank, src, hoje=self.day + timedelta(days=1))
        real = ss.iniciar
        captured = []
        def interrupt(bank, manifest):
            captured.append(manifest)
            real(bank, manifest)
            raise OSError('manifesto persistido')
        with patch.object(ss, 'iniciar', side_effect=interrupt), self.assertRaises(OSError):
            executar(plan)
        refs = captured[0]['referencias_rede']
        self.assertEqual(refs, [{'nome': snapshot.relative_to(first.banco).as_posix(),
                                'sha256': digest}])
        self.assertIn('/', refs[0]['nome'])
        self.assertNotIn('\\', refs[0]['nome'])
        ss._verificar_referencias(self.bank, captured[0])
        self.assertEqual(hashlib.sha256(snapshot.read_bytes()).hexdigest(), digest)
        with ss.bloquear(self.bank):
            ss.recuperar_concluida(self.bank)
        self.assertFalse(ss.pendencias(self.bank))
        self.assertEqual(src.read_bytes(), dados(linha('B', data='13/11/2026')))

    def test_unsafe_reference_paths_remain_rejected(self):
        import hashlib
        first = self.import_rows(linha('A'))
        digest = hashlib.sha256(first.geral.read_bytes()).hexdigest()
        relative = first.geral.relative_to(first.banco).as_posix()
        for name in ('../' + relative, str(first.geral.absolute()),
                     relative.replace('/', '\\'), 'C:/' + relative,
                     '/'+relative, '2026/../' + relative):
            with self.subTest(name=name), self.assertRaises(ValueError):
                ss._verificar_referencias(self.bank, {'referencias_rede': [
                    {'nome': name, 'sha256': digest}]})
