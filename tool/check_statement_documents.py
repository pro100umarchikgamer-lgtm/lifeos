"""Browser-local extraction of synthetic bank PDF and XLSX files."""
from argparse import ArgumentParser
from base64 import b64encode
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import os
from pathlib import Path
from threading import Thread
from zipfile import ZipFile, ZIP_DEFLATED
from playwright.sync_api import sync_playwright

ASSETS = Path(__file__).resolve().parents[1] / 'backend' / 'webassets' / 'app'


def statement_pdf(*pages, protected=False):
    objects = [b'<</Type /Catalog /Pages 2 0 R>>', b'',
               b'<</Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding>>']
    page_ids = []
    for lines in pages:
        stream = b'q 0.95 g 20 20 520 20 re f Q\n'
        for y, cells in lines:
            for x, text in cells:
                stream += f'BT /F1 10 Tf {x} {y} Td ({text}) Tj ET\n'.encode('ascii')
        page_id = len(objects) + 1
        page_ids.append(f'{page_id} 0 R')
        objects.extend([
            f'<</Type /Page /Parent 2 0 R /MediaBox [0 0 620 800] /Resources <</Font <</F1 3 0 R>>>> /Contents {page_id+1} 0 R>>'.encode(),
            f'<</Length {len(stream)}>>\nstream\n'.encode() + stream + b'endstream',
        ])
    objects[1] = f'<</Type /Pages /Count {len(pages)} /Kids [{" ".join(page_ids)}]>>'.encode()
    encryption = ''
    if protected:
        encryption = f'/Encrypt {len(objects) + 1} 0 R /ID [<{"f" * 32}> <{"f" * 32}>]'
        objects.append(f'<</Filter /Standard /V 1 /R 2 /O <{"1" * 64}> /U <{"2" * 64}> /P -4>>'.encode())
    pdf = b'%PDF-1.4\n'
    offsets = []
    for index, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf += f'{index} 0 obj\n'.encode() + obj + b'\nendobj\n'
    xref = f'xref\n0 {len(offsets)+1}\n0000000000 65535 f \n'
    xref += ''.join(f'{offset:010d} 00000 n \n' for offset in offsets)
    trailer = f'trailer\n<</Root 1 0 R /Size {len(offsets)+1} {encryption}>>\nstartxref\n{len(pdf)}\n%%EOF\n'
    return pdf + (xref + trailer).encode()


def statement_xlsx(sheet=None, *, date_1904=False):
    book_ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    rel_ns = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
    package_ns = 'http://schemas.openxmlformats.org/package/2006/relationships'
    sheet = sheet or '''
      <row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c>
        <c r="C1" t="s"><v>2</v></c><c r="D1" t="s"><v>3</v></c></row>
      <row r="2"><c r="A2" s="1"><v>2.5</v></c><c r="B2"><v>-1234.56</v></c>
        <c r="C2" t="inlineStr"><is><r><t>Corner </t></r><r><t>shop</t></r></is></c>
        <c r="D2" t="inlineStr"><is><t>RUB</t></is></c></row>
      <row r="3"><c r="A3" t="d"><v>2026-11-11</v></c><c r="B3"><f>2+2</f><v>4</v></c>
        <c r="D3" t="inlineStr"><is><t>USD</t></is></c></row>'''
    buffer = BytesIO()
    with ZipFile(buffer, 'w', compression=ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>')
        archive.writestr('xl/workbook.xml', f'''<workbook xmlns="{book_ns}" xmlns:r="{rel_ns}">
          <workbookPr date1904="{int(date_1904)}"/><sheets><sheet name="Operations" sheetId="1" r:id="rId1"/></sheets></workbook>''')
        archive.writestr('xl/_rels/workbook.xml.rels', f'''<Relationships xmlns="{package_ns}">
          <Relationship Id="rId1" Type="{rel_ns}/worksheet" Target="worksheets/sheet1.xml"/>
          <Relationship Id="rId2" Type="{rel_ns}/sharedStrings" Target="sharedStrings.xml"/>
          <Relationship Id="rId3" Type="{rel_ns}/styles" Target="styles.xml"/></Relationships>''')
        archive.writestr('xl/sharedStrings.xml', f'<sst xmlns="{book_ns}">' +
                         ''.join(f'<si><t>{label}</t></si>' for label in ['Date', 'Amount', 'Description', 'Currency']) + '</sst>')
        archive.writestr('xl/styles.xml', f'<styleSheet xmlns="{book_ns}"><cellXfs><xf numFmtId="0"/><xf numFmtId="14"/></cellXfs></styleSheet>')
        archive.writestr('xl/worksheets/sheet1.xml', f'<worksheet xmlns="{book_ns}"><sheetData>{sheet}</sheetData></worksheet>')
    return buffer.getvalue()


class StaticAssets(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self'; connect-src 'self'; worker-src 'self'")
        super().end_headers()


def run(engine):
    columns = ((40, 'Date'), (145, 'Description'), (390, 'Amount'), (475, 'Currency'), (530, 'Transaction ID'))
    page1 = [(740, columns),
             (719, ((40, '11.11.2026'), (145, 'Corner shop'), (372, '-1 234,56'), (475, 'RUB'), (530, 'AB-1'))),
             (707, ((145, 'Purchase reference'),)),
             (650, ((40, '11.11.2026'), (145, 'Closing balance'), (374, '99 999,00'), (475, 'RUB')))]
    page2 = [(740, columns),
             (719, ((40, '2026-11-12'), (145, 'Salary'), (392, '12.34'), (475, 'USD'), (530, 'AB-2')))]
    two_columns = [(740, ((40, 'Date'), (145, 'Description'), (360, 'Debit'), (420, 'Credit'), (475, 'Currency'))),
                   (719, ((40, '13.11.2026'), (145, 'Groceries'), (355, '1,15'), (475, 'EUR'))),
                   (705, ((40, '14.11.2026'), (145, 'Refund'), (420, '1,15'), (475, 'EUR'))),
                   (691, ((40, '15.11.2026'), (145, 'Both amounts'), (355, '9,99'), (420, '1,15'), (475, 'EUR')))]
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(StaticAssets, directory=ASSETS))
    origin = f'http://127.0.0.1:{server.server_port}'
    Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as playwright:
            launch = {'executable_path': os.environ['CHROMIUM_PATH']} if engine == 'chromium' and 'CHROMIUM_PATH' in os.environ else {}
            browser = getattr(playwright, engine).launch(**launch)
            page = browser.new_page()
            external = []
            page.on('request', lambda request: external.append(request.url) if not request.url.startswith(origin + '/') else None)
            page.goto(origin + '/index.html')
            def extract(module, data):
                return page.evaluate('''async ({module, data}) => {
                    const parser = await import(module === 'Pdf' ? '/statement-pdf.js' : '/statement-xlsx.js');
                    const bytes = Uint8Array.from(atob(data), char => char.charCodeAt(0));
                    try { return await parser['extractStatement' + module](bytes); }
                    catch (error) { return {error: error.code || String(error)}; }
                }''', {'module': module, 'data': b64encode(data).decode('ascii')})
            result = extract('Pdf', statement_pdf(page1, page2))
            assert result['rows'][1:] == [
                ['11.11.2026', '-1 234,56', 'Corner shop Purchase reference', 'RUB', 'AB-1', ''],
                ['2026-11-12', '12.34', 'Salary', 'USD', 'AB-2', ''],
            ], result
            assert result['needsReview']
            if engine == 'chromium':
                printable = browser.new_page()
                printable.set_content("""
                  <meta charset="utf-8">
                  <table style="font: 14px sans-serif; width: 660px; text-align: left">
                    <tr><th>Дата операции</th><th>Описание операции</th><th>Сумма операции</th><th>Валюта</th></tr>
                    <tr><td>11.11.2026</td><td>Тестовая покупка</td><td>-1 234,56</td><td>RUB</td></tr>
                  </table>
                """)
                localized = extract('Pdf', printable.pdf())
                printable.close()
                assert localized.get('rows', [None])[1:] == [
                    ['11.11.2026', '-1 234,56', 'Тестовая покупка', 'RUB', '', ''],
                ], localized
                assert localized['needsReview']
            fx = [(765, ((40, 'Account currency: RUB'),)),
                  (740, ((40, 'Date'), (115, 'Description'), (205, 'Amount'),
                         (265, 'Currency'), (330, 'Amount in account currency'))),
                  (720, ((40, '2026-11-10'), (115, 'Total market'), (205, '-10.00'),
                         (265, 'USD'), (330, '-900.00')))]
            assert extract('Pdf', statement_pdf(fx))['rows'][1][:4] == [
                '2026-11-10', '-900.00', 'Total market', 'RUB']
            assert extract('Pdf', statement_pdf(fx[1:]))['rows'][1][1] == ''

            debit_credit = extract('Pdf', statement_pdf(two_columns))['rows'][1:]
            assert [row[1] for row in debit_credit] == ['-1,15', '+1,15', ''], debit_credit
            assert extract('Pdf', statement_pdf([])) == {'error': 'import_pdf_scanned'}
            assert extract('Pdf', statement_pdf(page1, [])) == {'error': 'import_pdf_scanned'}
            assert extract('Pdf', statement_pdf(page1, protected=True)) == {'error': 'import_pdf_encrypted'}
            assert extract('Pdf', statement_pdf([(740, ((40, 'Text only'),))])) == {'error': 'import_pdf_layout'}
            assert extract('Pdf', b'Not a PDF') == {'error': 'import_format'}
            xlsx = extract('Xlsx', statement_xlsx(date_1904=True))
            assert xlsx['rows'] == [
                ['Date', 'Amount', 'Description', 'Currency'],
                ['1904-01-03', '-1234.56', 'Corner shop', 'RUB'],
                ['2026-11-11', '\ufffd', '', 'USD'],
            ], xlsx
            assert extract('Xlsx', statement_xlsx('<!DOCTYPE sheetData><row/>')) == {'error': 'import_xlsx_layout'}
            assert extract('Xlsx', b'Not a spreadsheet') == {'error': 'import_xlsx_layout'}
            assert not external, external
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
    print(f'{engine}: PDF tables, limits and XLSX cell decoding passed')


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('--engine', choices=('chromium', 'firefox', 'webkit'), default='chromium')
    run(parser.parse_args().engine)
