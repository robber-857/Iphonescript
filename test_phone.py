import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError
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
            self.assertIn('&lt;test&gt; &amp; alert',payload['Twiml'][0])
            self.assertEqual(payload['TimeLimit'],['60'])
            with self.assertRaises(ValueError):
                Phone(self.temp.name).call('again',lambda _:None,test=True)
            self.assertEqual(request.call_count,1)

    def test_disabled_daily_limit_and_uncertain_failure(self):
        self.phone.configure(dict(enabled=False))
        self.assertFalse(self.phone.call('disabled',lambda _:None))
        done=threading.Event(); reports=[]
        with patch('phone.urlopen',side_effect=URLError('contains-secret-do-not-log')):
            self.phone.call('test',lambda msg:(reports.append(msg),done.set()),test=True)
            self.assertTrue(done.wait(3))
        self.assertNotIn('contains-secret',reports[0])
        self.phone.usage.update(last_attempt=0,count=3)
        with self.assertRaises(ValueError):
            self.phone.call('daily limit',lambda _:None,test=True)

if __name__=='__main__':unittest.main()