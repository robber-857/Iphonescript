import copy
import json
import threading
import time
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import server

class BackendTests(unittest.TestCase):
    def setUp(self):
        self.original=copy.deepcopy(server.STATE)
        server.STATE.update(enabled=True,model='duo',postcode='2000',running=False,next_check=0,task=None,queue=[],results={},events=[],clear_apple_cookies=False,cookie_cleanup=None)
        server.PENDING_PHONE.clear()
        self.mock_phone=patch.object(server.PHONE,'call').start()
        self.mock_save=patch.object(server,'save').start()
        self.mock_notify=patch.object(server,'notify').start()
        self.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        threading.Thread(target=self.http.serve_forever,daemon=True).start()

    def tearDown(self):
        self.http.shutdown();self.http.server_close()
        server.STATE.clear();server.STATE.update(self.original)
        patch.stopall()

    def request(self,path,payload=None,token=True):
        headers={'Host':'127.0.0.1:8765'}
        if token:headers['X-Duo-Token']=server.TOKEN
        body=None if payload is None else json.dumps(payload).encode()
        req=Request(f'http://127.0.0.1:{self.http.server_port}'+path,data=body,headers=headers)
        with urlopen(req) as r:return json.load(r)

    def test_full_cycle_and_dedup(self):
        for i in range(8):
            task=self.request('/api/collector/task')['task']
            rows=[dict(store_id=sid,store=name,status='unavailable',message='Currently unavailable') for sid,name in server.STORES.items()]
            self.request('/api/collector/result',dict(id=task['id'],stores=rows))
        self.assertIsNone(self.request('/api/collector/task')['task'])
        self.assertEqual(len(server.STATE['results']),8)
        self.assertFalse(server.STATE['running'])
        self.assertGreater(server.STATE['next_check'],time.time())
        self.mock_notify.assert_not_called()

    def test_cleanup_blocks_next_cycle_until_ack_and_then_waits(self):
        server.STATE.update(clear_apple_cookies=True,running=True,queue=[],interval=60)
        response=self.request('/api/collector/task')
        cleanup=response['cleanup']
        self.assertTrue(cleanup)
        self.assertIsNone(server.STATE['next_check'])
        self.assertEqual(self.request('/api/collector/task')['cleanup'],cleanup)
        self.request('/api/collector/cleanup',dict(id=cleanup,error=False))
        self.assertAlmostEqual(server.STATE['next_check']-time.time(),60,delta=2)
        self.assertIsNone(self.request('/api/collector/task')['task'])

    def test_cleanup_failure_pauses_and_wrong_ack_is_rejected(self):
        server.STATE.update(clear_apple_cookies=True,running=True,queue=[])
        cleanup=self.request('/api/collector/task')['cleanup']
        with self.assertRaises(HTTPError):
            self.request('/api/collector/cleanup',dict(id='wrong',error=False))
        self.request('/api/collector/cleanup',dict(id=cleanup,error=True))
        self.assertFalse(server.STATE['enabled'])
        self.assertIsNone(server.STATE['next_check'])

    def test_error_preserves_last_success(self):
        task=self.request('/api/collector/task')['task']
        server.STATE['results'][task['variant']['id']]={'stores':[{'store_id':'R238','status':'available'}],'checked':123}
        self.request('/api/collector/result',dict(id=task['id'],error='HTTP 541'))
        result=server.STATE['results'][task['variant']['id']]
        self.assertEqual(result['checked'],123)
        self.assertEqual(result['stores'][0]['status'],'available')
        self.assertEqual(result['error'],'HTTP 541')

    def test_mutation_requires_token(self):
        with self.assertRaises(HTTPError) as ctx:self.request('/api/start',{},token=False)
        self.assertEqual(ctx.exception.code,403)

    def test_postcode_validation_and_new_task(self):
        old=self.request('/api/collector/task')['task']
        server.STATE['results']={'old':{'checked':1}}
        for invalid in ('200','20000','abcd','２０００'):
            with self.assertRaises(HTTPError) as ctx:
                self.request('/api/settings',dict(postcode=invalid,interval=300,notifications=True))
            self.assertEqual(ctx.exception.code,400)
        self.request('/api/settings',dict(postcode='2150',interval=300,notifications=True))
        self.assertEqual(server.STATE['results'],{})
        task=self.request('/api/collector/task')['task']
        self.assertEqual(task['postcode'],'2150')
        self.assertNotEqual(task['id'],old['id'])
        with self.assertRaises(HTTPError):
            self.request('/api/collector/result',dict(id=task['id'],postcode='2000',error='old collector'))

    def test_supported_intervals_and_schedule(self):
        for interval in (30,60,120,300):
            self.request('/api/settings',dict(postcode='2000',interval=interval,notifications=True))
            self.assertEqual(server.STATE['interval'],interval)
            self.assertAlmostEqual(server.STATE['next_check']-time.time(),interval,delta=2)
        for interval in (0,29,600,900,1800):
            with self.assertRaises(HTTPError) as ctx:
                self.request('/api/settings',dict(postcode='2000',interval=interval,notifications=True))
            self.assertEqual(ctx.exception.code,400)

    def test_pro_switch_and_no_auto_call(self):
        old=self.request('/api/collector/task')['task']
        self.request('/api/settings',dict(model='pro-test',postcode='2000',interval=30,notifications=True))
        task=self.request('/api/collector/task')['task']
        self.assertEqual(task['variant']['model'],'iPhone 18 Pro')
        with self.assertRaises(HTTPError):
            self.request('/api/collector/result',dict(id=old['id'],error='stale'))
        rows=[dict(store_id=sid,store=name,status='available',message='Available Tomorrow') for sid,name in server.STORES.items()]
        self.request('/api/collector/result',dict(id=task['id'],stores=rows))
        self.assertIsNone(self.request('/api/collector/task')['task'])
        self.mock_notify.assert_called_once()
        self.mock_phone.assert_not_called()
        self.assertEqual(len(server.STATE['results']),1)

    def test_duo_phone_aggregated_once_per_cycle(self):
        for i in range(8):
            task=self.request('/api/collector/task')['task']
            rows=[dict(store_id=sid,store=name,status='available',message='Available Tomorrow') for sid,name in server.STORES.items()]
            self.request('/api/collector/result',dict(id=task['id'],stores=rows))
        self.request('/api/collector/task')
        self.mock_phone.assert_called_once()
        self.assertIn('iPhone Duo',self.mock_phone.call_args.args[0])

    def test_pause_cancels_lease(self):
        self.request('/api/collector/task')
        self.request('/api/pause',{})
        self.assertIsNone(self.request('/api/collector/task')['task'])
        self.assertFalse(server.STATE['running'])

    def test_real_notification_path_and_no_duplicate(self):
        task=self.request('/api/collector/task')['task']
        rows=[dict(store_id=sid,store=name,status='available' if sid=='R238' else 'unavailable',message='Available today' if sid=='R238' else 'Currently unavailable') for sid,name in server.STORES.items()]
        self.request('/api/collector/result',dict(id=task['id'],stores=rows))
        self.mock_notify.assert_called_once()
        self.assertIn('Apple Sydney',self.mock_notify.call_args.args[0])
        server.STATE.update(running=False,queue=[],next_check=0)
        repeated=self.request('/api/collector/task')['task']
        self.request('/api/collector/result',dict(id=repeated['id'],stores=rows))
        self.mock_notify.assert_called_once()

if __name__=='__main__':unittest.main()
