"""Conservative PIN extraction and dependency-free XLSX export."""
import io
import re
import zipfile
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from xml.sax.saxutils import escape


class TextHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.hidden += 1
        if tag in ('br', 'p', 'div', 'tr', 'td', 'li'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.hidden = max(0, self.hidden - 1)
        if tag in ('p', 'div', 'tr', 'td', 'li'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


PIN = re.compile(r'(?i)(?<![\w])(?:PIN(?:\s*(?:number|code|no\.?))?|礼品卡密码|兑换码|卡密)\s*[:：#=\-]?\s*([A-Z0-9]{4,32})(?![A-Z0-9])')


def extract(raw, uid):
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    parts = []
    for part in msg.walk():
        if part.get_content_disposition() == 'attachment' or part.is_multipart():
            continue
        if part.get_content_type() not in ('text/plain', 'text/html'):
            continue
        body = part.get_content()
        if part.get_content_type() == 'text/html':
            parser = TextHTML()
            parser.feed(body)
            body = ''.join(parser.parts)
        parts.append(body)
    body = '\n'.join(parts)
    pins = []
    for match in PIN.finditer(body):
        pin = match.group(1)
        # Do not turn prose such as "PIN number below" into a redeemable code.
        if (any(c.isdigit() for c in pin) or re.fullmatch(r'X[A-Z]{15}', pin)) and pin not in pins:
            pins.append(pin)
    base = dict(uid=str(uid), subject=str(msg.get('Subject', '(无主题)')),
                sender=str(msg.get('From', '')), date=str(msg.get('Date', '')))
    return [dict(base, pin=pin, status='已提取') for pin in pins] or [dict(base, pin='', status='待核对')]


def workbook(rows):
    """All cells are inline strings: preserve leading zeroes and prevent formulas."""
    columns = [('pin', 'PIN'), ('status', '状态'), ('subject', '邮件主题'),
               ('sender', '发件人'), ('date', '邮件日期'), ('uid', '邮件 UID'), ('error', '备注')]
    matrix = [[label for _, label in columns]] + [[str(row.get(key, '')) for key, _ in columns] for row in rows]
    xmlrows = []
    for index, row in enumerate(matrix, 1):
        cells = []
        for col, value in enumerate(row):
            value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]', '', value)[:32767]
            cells.append(f'<c r="{chr(65+col)}{index}" t="inlineStr"><is><t xml:space="preserve">{escape(value)}</t></is></c>')
        xmlrows.append(f'<row r="{index}">' + ''.join(cells) + '</row>')
    sheet = '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="2" width="24" customWidth="1"/><col min="3" max="5" width="48" customWidth="1"/></cols><sheetData>' + ''.join(xmlrows) + f'</sheetData><autoFilter ref="A1:G{len(matrix)}"/></worksheet>'
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        z.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="礼品卡 PIN" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml', sheet)
    return out.getvalue()
