import sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
from controller.ofx_functions import carregar_ofx, pegar_dia_insterseccao, pegar_infos_transacoes, remove_anteriores, remove_transacao, salvar_ofx, junta_transacoes
from controller.browse_folders import get_name_ofx
header = 'OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\nENCODING:USASCII\nCHARSET:1252\nCOMPRESSION:NONE\nOLDFILEUID:NONE\nNEWFILEUID:NONE\n\n'
def fixture(items):
    tx = ''.join(f'<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>{date}<TRNAMT>{amount}<FITID>{ident}<CHECKNUM>{ident}<MEMO>{memo}</STMTTRN>' for date,amount,ident,memo in items)
    return header + '<OFX><SIGNONMSGSRSV1><SONRS><STATUS><CODE>0<SEVERITY>INFO</STATUS><DTSERVER>20230103120000<LANGUAGE>POR</SONRS></SIGNONMSGSRSV1><BANKMSGSRSV1><STMTTRNRS><TRNUID>1<STATUS><CODE>0<SEVERITY>INFO</STATUS><STMTRS><CURDEF>BRL<BANKACCTFROM><BANKID>1<ACCTID>123<ACCTTYPE>CHECKING</BANKACCTFROM><BANKTRANLIST><DTSTART>20230101120000<DTEND>20230103120000' + tx + '</BANKTRANLIST><LEDGERBAL><BALAMT>100<DTASOF>20230103120000</LEDGERBAL></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>'
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    common = ('20230102120000', '20', '2', 'Common')
    (root/'old.ofx').write_text(fixture([common]))
    (root/'Extrato.ofx').write_text(fixture([('20230101120000','10','1','Earlier'), common, ('20230103120000','30','3','New')]))
    _, old = carregar_ofx(str(root/'old.ofx'))
    h, current = carregar_ofx(str(root/'Extrato.ofx'))
    day = pegar_dia_insterseccao(current, '2023-01-02')
    assert day == '2023-01-02'
    assert pegar_infos_transacoes(current, day) == pegar_infos_transacoes(old, day)
    current = remove_anteriores(current, day)
    current = remove_transacao(current, '2')
    assert [t.fitid for t in current.statements[0].transactions] == ['3']
    output = salvar_ofx(current, h, str(root/'out'), 'output.ofx')
    _, restored = carregar_ofx(output)
    assert [t.fitid for t in restored.statements[0].transactions] == ['3']
    assert len(junta_transacoes(old, restored).statements[0].transactions) == 2
    print('PASS: parsing, overlap, filtering, deduplication, serialization/reparse and merging')
    found = get_name_ofx(str(root), 'Extrato')
    assert not Path(found).exists(), 'Update diagnosis: Windows path issue no longer reproduced'
    assert Path(output).parent != root/'out'
    print('CONFIRMED REPOSITORY LIMITATION: discovery and save use Windows backslashes on Linux')
