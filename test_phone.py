import json
import io
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs
from phone import Phone

class PhoneTests(unittest.TestCase):
    def setUp(self):
        scratch=Path(__file__).parent/'.tmp'
        scratch.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=scratch)
        self.phone=Phone(self.temp.name)
        self.cfg=dict(enabled=True,sid='AC'+'0'*32,token='1'*32,**{'from':'+61400000001','to':'+61400000002'})
        self.phone.configure(self.cfg)

    def tearDown(self):
        self.temp.cleanup()

    def test_status_never_exposes_credentials(self):
        text=json.dumps(self.phone.status())
        for key in ('sid','token','from','to'):
            self.assertNotIn(self.cfg[key],text)
        self.phone.configure(dict(enabled=False))
        self.assertEqual(Phone(self.temp.name).config['token'],self.cfg['token'])

    def test_call_payload_and_persistent_cooldown(self):
        done=threading.Event()
        with patch('phone.urlopen') as request:
            request.return_value.__enter__.return_value.read.return_value=b'{"sid":"CAexample"}'
            self.phone.call('Stock <test> & alert',lambda msg:done.set())
            self.assertTrue(done.wait(3))
            args=request.call_args.args[0]
            payload=parse_qs(args.data.decode())
            self.assertEqual(payload['To'],[self.cfg['to']])
            self.assertEqual(set(payload), {'To', 'From', 'Url'})
            self.assertEqual(payload['Url'], ['https://webhooks.twilio.com/v1/Voice/Template/voice_text_to_speech'])
            self.assertNotIn('Stock', args.data.decode())
            with self.assertRaises(ValueError):
                Phone(self.temp.name).call('again',lambda _:None,test=True)
            self.assertEqual(request.call_count,1)

    def test_disabled_and_uncertain_failure(self):
        self.phone.configure(dict(enabled=False))
        self.assertFalse(self.phone.call('disabled',lambda _:None))
        done=threading.Event(); reports=[]
        with patch('phone.urlopen',side_effect=URLError('contains-secret-do-not-log')):
            self.phone.call('test',lambda msg:(reports.append(msg),done.set()),test=True)
            self.assertTrue(done.wait(3))
        self.assertNotIn('contains-secret',reports[0])

    def test_provider_error_is_actionable_and_redacted(self):
        detail = json.dumps(dict(code=21212, message='Invalid From ' + self.cfg['from'] + ' ' + self.cfg['token'])).encode()
        error = HTTPError('https://api.twilio.com', 400, 'Bad Request', {}, io.BytesIO(detail))
        done = threading.Event()
        reports = []
        with patch('phone.urlopen', side_effect=error):
            self.phone.call('test', lambda msg: (reports.append(msg), done.set()), test=True)
            self.assertTrue(done.wait(3))
        self.assertIn('Twilio 21212', reports[0])
        self.assertIn('Invalid From', reports[0])
        for key in ('token', 'from'):
            self.assertNotIn(self.cfg[key], reports[0])

    def test_non_json_provider_error_preserves_report(self):
        error = HTTPError('https://api.twilio.com', 502, 'Bad Gateway', {}, io.BytesIO(b'<html>error</html>'))
        done = threading.Event()
        reports = []
        with patch('phone.urlopen', side_effect=error):
            self.phone.call('test', lambda msg: (reports.append(msg), done.set()), test=True)
            self.assertTrue(done.wait(3))
        self.assertIn('HTTP 502', reports[0])

    def test_one_minute_boundary_and_no_daily_limit_after_restart(self):
        for test in (False, True):
            with self.subTest(test=test):
                self.phone.usage.update(last_attempt=1000,count=100,day=datetime.now(timezone.utc).date().isoformat())
                self.phone.write('phone-usage.json',self.phone.usage)
                restored=Phone(self.temp.name)
                done=threading.Event()
                with patch('phone.urlopen') as request:
                    request.return_value.__enter__.return_value.read.return_value=b'{"sid":"CAexample"}'
                    with patch('phone.time.time',return_value=1059):
                        with self.assertRaisesRegex(ValueError,'1 分钟'):
                            restored.call('too soon',lambda _:None,test=test)
                    request.assert_not_called()
                    with patch('phone.time.time',return_value=1060):
                        self.assertTrue(restored.call('allowed',lambda _:done.set(),test=test))
                        self.assertTrue(done.wait(3))
                    self.assertEqual(request.call_count,1)

if __name__=='__main__':unittest.main()
