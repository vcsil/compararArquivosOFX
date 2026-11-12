import io
import tempfile
import unittest
import warnings
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path
from test_baseline import A, HEADER, fixture, make
from controller.ofx_functions import carregar_ofx, salvar_ofx
from controller.ofx_io import OFXEncodingWarning, serializar_ofx
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
        (h,o),w=self.read(fixture([('20230102120000','20','2','Café')],'utf-8'))
        self.assertEqual(o.statements[0].transactions[0].memo,'Café'); self.assertTrue(w)
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
if __name__ == '__main__': unittest.main()
