import io
import json
import unittest
import threading
import time
import zipfile
from email.message import EmailMessage
from unittest.mock import patch
from xml.etree import ElementTree as ET
import server
import google_auth
from urllib.parse import urlparse, parse_qs
from extract import extract, workbook


def mail(body, html=False):
    msg = EmailMessage()
    msg['Subject'] = '=HYPERLINK("bad")'
    msg['From'] = 'Sender <test@example.com>'
    msg.set_content(body, subtype='html' if html else 'plain')
    return msg.as_bytes()


class Tests(unittest.TestCase):
    def test_pause_resume_keeps_cursor_and_no_duplicate_reads(self):
        entered = threading.Event()
        release = threading.Event()
        class Fake:
            def __init__(self): self.reads=[]
            def read(self, uid):
                self.reads.append(uid)
                if uid=='1':
                    entered.set()
                    if not release.wait(3): raise RuntimeError('test timeout')
                return mail('PIN: 001234')
        fake=Fake()
        with patch.object(server,'CLIENT',fake),patch.dict(server.STATE,rows=[],cursor=0,busy=True,pause_requested=False,paused=False):
            server.RESUME.set()
            worker=threading.Thread(target=server.run_job,args=(server.fetch_batch,['1','2','3']))
            worker.start()
            try:
                self.assertTrue(entered.wait(3))
                with server.LOCK:
                    server.STATE['pause_requested']=True
                    server.RESUME.clear()
                release.set()
                deadline=time.monotonic()+3
                while not server.STATE['paused'] and time.monotonic()<deadline: time.sleep(.01)
                self.assertTrue(server.STATE['paused'])
                self.assertEqual(fake.reads,['1'])
                self.assertEqual(server.STATE['cursor'],1)
                self.assertEqual(len(server.STATE['rows']),1)
            finally:
                with server.LOCK: server.STATE['pause_requested']=False
                release.set();server.RESUME.set();worker.join(3)
            self.assertFalse(worker.is_alive())
            self.assertEqual(fake.reads,['1','2','3'])
            self.assertEqual(server.STATE['cursor'],3)
            self.assertEqual(len(server.STATE['rows']),3)
            self.assertFalse(server.STATE['busy'])
            self.assertFalse(server.STATE['batch_running'])

    def test_apple_forward_html(self):
        rows = extract(mail('<div>Your Gift Card PIN</div><table><tr><td>XABC1234TEST56789</td></tr></table>', True), '7')
        self.assertEqual(rows[0]['pin'], 'XABC1234TEST56789')

    def test_multiple_pins_and_duplicate(self):
        rows = extract(mail('PIN number: 001234\nPIN: X1234ABC\nPIN: 001234'), '8')
        self.assertEqual([r['pin'] for r in rows], ['001234', 'X1234ABC'])

    def test_prose_and_order_number_not_pin(self):
        rows = extract(mail('PIN number below. Order number: 12345678\nGift Card Value: A$1,750'), '9')
        self.assertEqual(rows[0]['status'], '待核对')

    def test_hidden_script(self):
        self.assertFalse(extract(mail('<script>PIN: 123456</script><div>No PIN here</div>', True), '1')[0]['pin'])

    def test_attachment_not_body(self):
        msg=EmailMessage();msg.set_content('See attachment')
        msg.add_attachment(b'PIN: 123456', maintype='text', subtype='plain', filename='a.txt')
        self.assertFalse(extract(msg.as_bytes(), '1')[0]['pin'])

    def test_xlsx_preserves_strings_and_no_formulas(self):
        data=workbook([dict(pin='00123456789012345678', subject='=HYPERLINK("bad")')])
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist(): ET.fromstring(z.read(name))
            xml=z.read('xl/worksheets/sheet1.xml').decode()
            self.assertIn('00123456789012345678', xml)
            self.assertIn('=HYPERLINK', xml)
            self.assertNotIn('<f>', xml)

    def test_batches_and_readonly_fetch_and_retry(self):
        class Fake:
            def __init__(self):self.fail=True;self.fetches=[]
            def read(self, uid):
                self.fetches.append(uid)
                if uid=='5' and self.fail:raise OSError('offline')
                return mail('PIN: 001234')
        fake=Fake()
        with patch.object(server,'CLIENT',fake),patch.dict(server.STATE,rows=[],cursor=0):
            server.fetch_batch([str(x) for x in range(100)])
            self.assertEqual(server.STATE['cursor'],100)
            self.assertEqual(len(server.STATE['rows']),100)
            self.assertEqual(server.STATE['rows'][5]['status'],'读取失败')
            fake.fail=False;server.fetch_batch(['5'],retry=True)
            self.assertEqual(len(server.STATE['rows']),100)
            self.assertEqual(server.STATE['cursor'],100)
            self.assertEqual(len(fake.fetches),101)

    def test_search_unicode_and_reset(self):
        class Fake:
            def search(self,query):self.query=query;return ['3','2','1']
        fake=Fake()
        with patch.object(server,'CLIENT',fake),patch.dict(server.STATE):
            server.search('礼品卡 subject:"Gift Card"')
            self.assertEqual(fake.query,'礼品卡 subject:"Gift Card"')
            self.assertEqual(server.STATE['ids'],['3','2','1'])
            self.assertEqual(server.STATE['rows'],[])

    def test_oauth_state_pkce_and_replay(self):
        auth=google_auth.OAuth()
        with patch.object(google_auth,'configuration',return_value=dict(client_id='test.apps.googleusercontent.com',client_secret='test')):
            url=auth.begin(8876,'test@example.com')
        query={k:v[0] for k,v in parse_qs(urlparse(url).query).items()}
        self.assertEqual(query['scope'],google_auth.SCOPE)
        self.assertEqual(query['code_challenge_method'],'S256')
        self.assertNotIn('client_secret',query)
        with self.assertRaises(ValueError):auth.consume({'state':'wrong','code':'test'})
        self.assertIsNotNone(auth.pending)
        pending=auth.consume({'state':query['state'],'code':'test'})
        self.assertGreaterEqual(len(pending['verifier']),43)
        with self.assertRaises(ValueError):auth.consume({'state':query['state'],'code':'test'})

    def test_oauth_expired_and_denied(self):
        auth=google_auth.OAuth()
        auth.pending=dict(state='valid',expires=0)
        with self.assertRaises(ValueError):auth.consume({'state':'valid'})
        auth.pending=dict(state='valid',expires=float('inf'))
        with self.assertRaises(ValueError):auth.consume({'state':'valid','error':'access_denied'})
        self.assertIsNone(auth.pending)

    def test_oauth_config_validation(self):
        with self.assertRaises(ValueError):google_auth.validate_config({'web':{}})
        with self.assertRaises(ValueError):google_auth.validate_config({'installed':None})
        self.assertEqual(google_auth.validate_config({'installed':dict(client_id='a.apps.googleusercontent.com',client_secret='b',token_uri='https://evil.invalid')})['client_secret'],'b')

    def test_api_pagination_and_refresh(self):
        client=google_auth.Gmail({'access_token':'test','refresh_token':'refresh'}, {})
        with patch.object(client,'get',side_effect=[{'messages':[{'id':'a'}],'nextPageToken':'p2'},{'messages':[{'id':'b'},{'id':'a'}]}]) as get:
            self.assertEqual(client.search('subject:test'),['a','b'])
            self.assertEqual(get.call_args.kwargs['pageToken'],'p2')
        client.expires=0
        with patch.object(google_auth,'http_json',side_effect=[{'access_token':'new','expires_in':3600},{'emailAddress':'test@example.com'}]) as http:
            self.assertEqual(client.get('profile')['emailAddress'],'test@example.com')
            self.assertEqual(http.call_args.kwargs['token'],'new')
        client.logout()
        self.assertEqual(client.tokens,{})

    def test_api_raw_read(self):
        import base64
        raw=mail('PIN: 001234')
        client=google_auth.Gmail({'access_token':'test'}, {})
        with patch.object(client,'get',side_effect=[{'sizeEstimate':100},{'raw':base64.urlsafe_b64encode(raw).decode().rstrip('=')}]) as get:
            self.assertEqual(client.read('abc123'),raw)
            self.assertEqual(get.call_args.kwargs['format'],'raw')


if __name__=='__main__':unittest.main()
