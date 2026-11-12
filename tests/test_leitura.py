import io
import contextlib
import runpy
import tempfile
import unittest
import warnings
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch
from test_baseline import A, HEADER, fixture, make
from controller.ofx_functions import carregar_ofx, salvar_ofx
from controller.ofx_io import OFXEncodingWarning, OFXEncodingAmbiguaError, serializar_ofx
from ofxtools.header import OFXHeaderV2
from ofxtools.Parser import OFXTree

class Leitura(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.path = self.root / 'original.ofx'
    def read(self, raw):
        self.path.write_bytes(raw)
        with warnings.catch_warnings(record=True) as notices:
            warnings.simplefilter('always')
            result = carregar_ofx(self.path)
        self.assertEqual(self.path.read_bytes(),raw)
        return result, notices
    def test_cp1252(self):
        (h,o),w=self.read(fixture([('20230102120000','20','2','Café')],'cp1252'))
        self.assertEqual(o.statements[0].transactions[0].memo,'Café'); self.assertFalse(w)
    def test_utf8_wrong_header_undefined_byte(self):
        (h,o),w=self.read(fixture([('20230102120000','20','2','PIX Í')],'utf-8'))
        self.assertEqual(o.statements[0].transactions[0].memo,'PIX Í'); self.assertTrue(any(isinstance(x.message,OFXEncodingWarning) for x in w))
    def test_utf8_wrong_header_ambiguous(self):
        raw=fixture([('20230102120000','20','2','Café')],'utf-8')
        self.path.write_bytes(raw)
        with self.assertRaises(OFXEncodingAmbiguaError): carregar_ofx(self.path)
        self.assertEqual(self.path.read_bytes(),raw)
        self.assertEqual(carregar_ofx(self.path,codificacao='utf-8')[1].statements[0].transactions[0].memo,'Café')
        self.assertEqual(carregar_ofx(self.path,codificacao='cp1252')[1].statements[0].transactions[0].memo,'CafÃ©')
        self.assertEqual(self.path.read_bytes(),raw)
        self.assertEqual(list(self.root.iterdir()),[self.path])
    def test_cp1252_genuino_ambiguous(self):
        raw=fixture([('20230102120000','20','2','CafÃ©')],'cp1252')
        self.path.write_bytes(raw)
        with self.assertRaises(OFXEncodingAmbiguaError): carregar_ofx(self.path)
        self.assertEqual(carregar_ofx(self.path,codificacao='cp1252')[1].statements[0].transactions[0].memo,'CafÃ©')
        self.assertEqual(carregar_ofx(self.path,codificacao='utf-8')[1].statements[0].transactions[0].memo,'Café')
        self.assertEqual(self.path.read_bytes(),raw)
    def test_fluxo_interativo_nao_grava_ambiguidade(self):
        raw=fixture([('20230102120000','20','2','Café')],'utf-8')
        self.path.write_bytes(raw)
        with patch('controller.user_navigation.define_diretorio',return_value=str(self.root)), \
             patch('controller.browse_folders.get_name_ofx',return_value=str(self.path)), \
             patch('controller.browse_folders.get_old_directory',return_value='nao-lido.ofx'), \
             patch('controller.ofx_functions.salvar_ofx') as save, \
             patch('controller.ofx_functions.salvar_ofx_geral') as save_general, \
             patch('builtins.input',return_value=''), contextlib.redirect_stdout(io.StringIO()):
            runpy.run_path(str(Path(__file__).resolve().parents[1]/'src'/'comparaArqOFX.py'),run_name='__main__')
        save.assert_not_called(); save_general.assert_not_called()
        self.assertEqual(self.path.read_bytes(),raw)
        self.assertEqual(list(self.root.iterdir()),[self.path])
    def test_invalid_explicit_choice(self):
        self.path.write_bytes(fixture([A]))
        with self.assertRaises(ValueError): carregar_ofx(self.path,codificacao='latin1')
        self.path.write_bytes(fixture([('20230102120000','20','2','Café')],'cp1252'))
        with self.assertRaises(UnicodeDecodeError): carregar_ofx(self.path,codificacao='utf-8')
    def test_utf8_recovery_requires_valid_structure(self):
        raw=HEADER + '<OFX><BROKEN>Í'.encode('utf-8')
        self.path.write_bytes(raw)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', OFXEncodingWarning)
            with self.assertRaises(Exception): carregar_ofx(self.path)
        self.assertEqual(self.path.read_bytes(),raw)
    def test_sgml_utf8_correct(self):
        data=fixture([('20230102120000','20','2','Café')],'utf-8').replace(b'CHARSET:1252',b'CHARSET:NONE')
        (h,o),w=self.read(data); self.assertEqual(o.statements[0].transactions[0].memo,'Café'); self.assertFalse(w)
    def test_xml_variants_and_bom(self):
        _,model=self.read(fixture([A]))[0]
        xml=serializar_ofx(model)
        for data in (xml, xml.replace(str(OFXHeaderV2(version=203)).encode(),b'<?xml version="1.0" encoding="UTF-8"?>\n'), b'\xef\xbb\xbf'+xml, xml[xml.index(b'<OFX>'):]):
            with self.subTest(prefix=data[:40]):
                (h,o),_=self.read(data); self.assertEqual(o.statements[0].transactions[0].fitid,'2')
    def test_empty_and_malformed(self):
        (h,o),_=self.read(fixture([])); self.assertEqual(len(o.statements[0].transactions),0)
        for data in (b'garbage',b'<?xml version="1.0"?><OFX>',b'OFXHEADER:100\n'):
            with self.subTest(data=data), self.assertRaises(Exception): self.read(data)
    def test_original_timezone_offset_preserved(self):
        data = fixture([('20230102120000[-3:EST]', '20', '2', 'Zona')])
        (h, model), _ = self.read(data)
        # Preserve o deslocamento local após a conversão do ofxtools.
        self.assertEqual(model.statements[0].transactions[0].dtposted.utcoffset().total_seconds(), -10800)
    def test_timezone_rollover_preserves_local_day(self):
        data = fixture([('20230102233000[-3:EST]', '20', '2', 'Noite')])
        (h, model), _ = self.read(data)
        t = model.statements[0].transactions[0]
        self.assertEqual(t.dtposted.strftime('%Y-%m-%d %H:%M'), '2023-01-02 23:30')
        self.assertEqual(t.dtposted.utcoffset().total_seconds(), -10800)
    def test_existing_output_is_not_overwritten(self):
        (h, model), _ = self.read(fixture([A]))
        target = self.root / 'out.ofx'
        target.write_bytes(b'existente')
        with self.assertRaises(FileExistsError):
            salvar_ofx(model, h, str(self.root), target.name)
        self.assertEqual(target.read_bytes(), b'existente')
    def test_old_output(self):
        import xml.dom.minidom
        parser=OFXTree(); parser.parse(io.BytesIO(fixture([A])))
        body=xml.dom.minidom.parseString(ET.tostring(parser.convert().to_etree())).toprettyxml(indent='\t')[23:]
        (h,o),_=self.read(HEADER+body.encode('utf-8')); self.assertEqual(o.statements[0].transactions[0].fitid,'2')
    def test_roundtrip_and_original_protection(self):
        item=('20230102120000[-3:EST]','123456789.12','ID-01','Café & Cia')
        # SGML original does not require XML escaping for ampersand.
        raw=fixture([item],'cp1252'); (h,o),_=self.read(raw)
        before=o.statements[0]; t=before.transactions[0]
        out=salvar_ofx(o,h,str(self.root),'out.ofx'); h2,o2=carregar_ofx(out)
        after=o2.statements[0]; t2=after.transactions[0]
        self.assertEqual((t.fitid,t.dtposted,t.trnamt,t.memo,t.trntype,t.checknum),(t2.fitid,t2.dtposted,t2.trnamt,t2.memo,t2.trntype,t2.checknum))
        self.assertEqual(t.dtposted.utcoffset().total_seconds(), -10800)
        self.assertEqual(t2.dtposted.utcoffset(), t.dtposted.utcoffset())
        self.assertEqual(t.trnamt,Decimal('123456789.12')); self.assertIsNotNone(t.dtposted.utcoffset())
        self.assertEqual((before.curdef,before.bankacctfrom.acctid,before.bankacctfrom.bankid,before.banktranlist.dtstart,before.banktranlist.dtend,before.ledgerbal.balamt),(after.curdef,after.bankacctfrom.acctid,after.bankacctfrom.bankid,after.banktranlist.dtstart,after.banktranlist.dtend,after.ledgerbal.balamt))
        self.assertEqual(self.path.read_bytes(),raw)
        with self.assertRaises(ValueError): salvar_ofx(o,h,str(self.root),'original.ofx')
        self.assertEqual(self.path.read_bytes(),raw)
    def test_saida_v2_ofxtools_e_leitor(self):
        raw=fixture([('20230102233000[-3:EST]','123.45','ID-123','Café & Cia')],'cp1252')
        (header,model),_=self.read(raw)
        output=salvar_ofx(model,header,str(self.root),'output.ofx')
        data=Path(output).read_bytes()
        self.assertTrue(data.startswith(b'<?xml version="1.0" encoding="UTF-8"'))
        self.assertIn(b'<?OFX OFXHEADER="200" VERSION="203"',data)
        parser=OFXTree(); parser.parse(io.BytesIO(data)); legacy=parser.convert().statements[0].transactions[0]
        new=carregar_ofx(output)[1].statements[0].transactions[0]
        self.assertEqual((legacy.fitid,legacy.trnamt,legacy.memo),('ID-123',Decimal('123.45'),'Café & Cia'))
        self.assertEqual((new.fitid,new.trnamt,new.memo),('ID-123',Decimal('123.45'),'Café & Cia'))
        self.assertEqual(new.dtposted.strftime('%Y-%m-%d %H:%M'),'2023-01-02 23:30')
        self.assertEqual(new.dtposted.utcoffset().total_seconds(),-10800)
        self.assertEqual(self.path.read_bytes(),raw)
if __name__ == '__main__': unittest.main()
