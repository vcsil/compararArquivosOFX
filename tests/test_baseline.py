import io, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from decimal import Decimal
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from controller import ofx_functions as f, browse_folders as b
from ofxtools.Parser import OFXTree

HEADER = b'OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\nENCODING:USASCII\nCHARSET:1252\nCOMPRESSION:NONE\nOLDFILEUID:NONE\nNEWFILEUID:NONE\n\n'
def make(items, account='123'):
    tx = ''.join(f'<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>{d}<TRNAMT>{v}<FITID>{i}<CHECKNUM>{i}<MEMO>{m}</STMTTRN>' for d,v,i,m in items)
    return ('<OFX><SIGNONMSGSRSV1><SONRS><STATUS><CODE>0<SEVERITY>INFO</STATUS><DTSERVER>20230103120000<LANGUAGE>POR</SONRS></SIGNONMSGSRSV1><BANKMSGSRSV1><STMTTRNRS><TRNUID>1<STATUS><CODE>0<SEVERITY>INFO</STATUS><STMTRS><CURDEF>BRL<BANKACCTFROM><BANKID>1<ACCTID>'+account+'<ACCTTYPE>CHECKING</BANKACCTFROM><BANKTRANLIST><DTSTART>20230101120000<DTEND>20230103120000'+tx+'</BANKTRANLIST><LEDGERBAL><BALAMT>100<DTASOF>20230103120000</LEDGERBAL></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>')
A=('20230102120000','20','2','Common')
def parse(data):
    p=OFXTree(); p.parse(io.BytesIO(data)); return p.convert()
def fixture(items, encoding='ascii', account='123'): return HEADER+make(items,account).encode(encoding)
def infos(o): return f.pegar_infos_transacoes(o,'2023-01-02')
def limpo_em(pasta):
    from controller.ofx_names import eh_nome_limpo
    arquivos = [p for p in Path(pasta).iterdir() if eh_nome_limpo(p.name)]
    if len(arquivos) != 1:
        raise AssertionError(f'Esperado um OFX Limpo em {pasta}: {arquivos}')
    return arquivos[0]

class Baseline(unittest.TestCase):
    def test_01_sgml(self): self.assertEqual(parse(fixture([A])).statements[0].transactions[0].fitid,'2')
    def test_02_xml_v2(self):
        from ofxtools.header import OFXHeaderV2
        body=OFXTree(); body.parse(io.BytesIO(fixture([A])))
        import xml.etree.ElementTree as ET
        data=(str(OFXHeaderV2(version=203))+'\n').encode()+ET.tostring(body.getroot())
        self.assertEqual(parse(data).statements[0].transactions[0].fitid,'2')
    def test_03_xml_without_ofx_declaration(self):
        with self.assertRaises(Exception): parse(b'<?xml version="1.0" encoding="UTF-8"?>\n<OFX></OFX>')
    def test_04_mislabeled_utf8_and_memory_normalization(self):
        item=('20230102120000','20','2','PIX Í')
        raw=fixture([item], 'utf-8')
        with self.assertRaises(UnicodeDecodeError) as exc: parse(raw)
        self.assertEqual(exc.exception.object[exc.exception.start],0x8d)
        normalized=raw.replace(b'CHARSET:1252',b'CHARSET:NONE',1)
        t=parse(normalized).statements[0].transactions[0]
        self.assertEqual((t.memo,t.fitid,t.trnamt,t.dtposted.strftime('%Y%m%d')),('PIX Í','2',Decimal('20'),'20230102'))
        self.assertEqual(parse(fixture([item],'cp1252')).statements[0].transactions[0].memo,'PIX Í')
    def test_05_empty_statement(self):
        o=parse(fixture([])); self.assertIsNone(f.pegar_dia_insterseccao(o,'2023-01-02'))
    def test_06_malformed(self):
        with self.assertRaises(Exception): parse(b'not an OFX')
    def test_07_duplicate_identical(self): self.assertEqual(infos(parse(fixture([A]))),infos(parse(fixture([A]))))
    @unittest.expectedFailure
    def test_08_distinct_ids_same_description_value(self):
        x=infos(parse(fixture([A])))[0]; y=infos(parse(fixture([('20230102120000','20','3','Common')])))[0]
        self.assertNotEqual(x[0],y[0], 'matching uses memo and value, discarding identity')
    @unittest.expectedFailure
    def test_09_same_fitid_changed_memo(self):
        x=infos(parse(fixture([A])))[0]; y=infos(parse(fixture([('20230102120000','20','2','Changed')])))[0]
        self.assertEqual(x[0],y[0], 'same FITID does not match changed memo')
    @unittest.expectedFailure
    def test_10_same_fitid_changed_amount(self):
        x=infos(parse(fixture([A])))[0]; y=infos(parse(fixture([('20230102120000','21','2','Common')])))[0]
        self.assertEqual(x[0],y[0], 'same FITID does not match changed amount')
    def test_11_no_last_date(self):
        with self.assertRaises(FileExistsError): f.pegar_dia_insterseccao(parse(fixture([A])),'2023-01-03')
    def test_12_prior_days(self):
        o=parse(fixture([('20230101120000','1','1','Old'),A])); f.remove_anteriores(o,'2023-01-02'); self.assertEqual([t.fitid for t in o.statements[0].transactions],['2'])
    @unittest.expectedFailure
    def test_13_reprocessing_accumulator(self):
        o=parse(fixture([A])); f.junta_transacoes(o,parse(fixture([A]))); self.assertEqual(len(o.statements[0].transactions),1)
    def test_14_create_and_update_general(self):
        o=parse(fixture([A]))
        with patch.object(f.os,'listdir',return_value=[]), patch.object(f,'salvar_ofx',return_value='created') as save:
            self.assertEqual(f.salvar_ofx_geral(o,'header',r'bank\2023-01-02\001'),'created'); self.assertIn('OFXGeral-2023-01-02.ofx',save.call_args.args)
        with patch.object(f.os,'listdir',return_value=['OFXGeral-2023-01-02.ofx']), patch.object(f,'carregar_ofx',return_value=('header',parse(fixture([A])))), patch.object(f,'salvar_ofx',return_value='updated') as save:
            self.assertEqual(f.salvar_ofx_geral(o,'header',r'bank\2023-01-02\001'),'updated'); self.assertEqual(len(save.call_args.args[0].statements[0].transactions),2)
    def test_15_missing_history(self):
        with patch.object(b.os,'listdir',side_effect=FileNotFoundError):
            with self.assertRaises(FileNotFoundError): b.get_old_directory(r'bank\day\001')
    @unittest.expectedFailure
    def test_16_different_accounts_rejected(self):
        o=parse(fixture([A],account='123')); other=parse(fixture([A],account='456'))
        with self.assertRaises(ValueError): f.junta_transacoes(o,other)
    @unittest.expectedFailure
    def test_17_unordered_directories(self):
        with patch.object(b.os,'listdir',return_value=['003','001','002']), patch.object(b,'get_name_ofx',side_effect=lambda d,*a,**k:d):
            self.assertTrue(b.get_old_directory('ignored',r'bank\day',subiu=True,nivel=-1).endswith('003'))
    @unittest.expectedFailure
    def test_18_write_failure_preserves_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'history'
            target.write_text('original')
            class Broken:
                def __enter__(self): target.write_text(''); return self
                def __exit__(self,*a): return False
                def write(self, data): raise OSError('simulated')
            with patch('builtins.open',return_value=Broken()):
                with self.assertRaises(OSError): f.salvar_ofx(parse(fixture([A])),'header',tmp,'history', _permitir_atualizar_historico=True)
            self.assertEqual(target.read_text(),'original')
if __name__=='__main__': unittest.main()
