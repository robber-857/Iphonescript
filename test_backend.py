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

# Synthetic stores only; never real inventory.
FIXTURE_STORES = {'R250': 'Fixture West 14th Street', 'R095': 'Fixture Fifth Avenue'}

class BackendTests(unittest.TestCase):
    def setUp(self):
        self.original=copy.deepcopy(server.STATE)
        server.STATE.update(enabled=True,model='duo',postcode='10001',running=False,next_check=0,task=None,queue=[],results={},events=[],clear_apple_cookies=False,cookie_cleanup=None)
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
        headers={'Host':'127.0.0.1:8766'}
        if token:headers['X-Duo-Token']=server.TOKEN
        if path=='/api/collector/result' and payload is not None:
            payload=dict(postcode=server.STATE['postcode'],scope_version=3,**payload) if 'postcode' not in payload and 'scope_version' not in payload else payload
        body=None if payload is None else json.dumps(payload).encode()
        req=Request(f'http://127.0.0.1:{self.http.server_port}'+path,data=body,headers=headers)
        with urlopen(req) as r:return json.load(r)

    def test_full_cycle_and_dedup(self):
        for i in range(8):
            task=self.request('/api/collector/task')['task']
            rows=[dict(store_id=sid,store=name,distance_km=5,status='unavailable',message='Currently unavailable') for sid,name in FIXTURE_STORES.items()]
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
        server.STATE['results'][task['variant']['id']]={'stores':[{'store_id':'R250','status':'available'}],'checked':123}
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
        for invalid in ('200','123456','abcd','２０００'):
            with self.assertRaises(HTTPError) as ctx:
                self.request('/api/settings',dict(postcode=invalid,interval=300,notifications=True))
            self.assertEqual(ctx.exception.code,400)
        self.request('/api/settings',dict(postcode='02108',interval=300,notifications=True))
        self.assertEqual(server.STATE['results'],{})
        task=self.request('/api/collector/task')['task']
        self.assertEqual(task['postcode'],'02108')
        self.assertNotEqual(task['id'],old['id'])
        with self.assertRaises(HTTPError):
            self.request('/api/collector/result',dict(id=task['id'],postcode='10001',error='old collector'))

    def test_zip_scope_and_old_collector_rejection(self):
        old=self.request('/api/collector/task')['task']
        self.request('/api/settings',dict(postcode='94105',interval=300,notifications=False))
        self.assertEqual(self.request('/api/state')['stores'],{})
        task=self.request('/api/collector/task')['task']
        rows=[dict(store_id='R999',store='Fixture SF store',distance_km=5,status='unavailable',message='Currently unavailable')]
        with self.assertRaises(HTTPError):
            self.request('/api/collector/result',dict(id=old['id'],postcode='94105',scope_version=3,stores=rows))
        with self.assertRaises(HTTPError):
            self.request('/api/collector/result',dict(id=task['id'],postcode='94105',stores=rows))
        self.request('/api/collector/result',dict(id=task['id'],postcode='94105',scope_version=3,stores=rows))
        self.assertEqual(self.request('/api/state')['stores'],{'R999':'Fixture SF store'})
        self.request('/api/settings',dict(postcode='10001',interval=300,notifications=False))
        self.assertEqual(self.request('/api/state')['stores'],{})
        self.assertEqual(server.STATE['results'],{})

    def test_supported_intervals_and_schedule(self):
        for interval in (30,60,120,300,600,900,1200,1800):
            self.request('/api/settings',dict(postcode='10001',interval=interval,notifications=True))
            self.assertEqual(server.STATE['interval'],interval)
            self.assertAlmostEqual(server.STATE['next_check']-time.time(),interval,delta=2)
        for interval in (0,29,301,1500,1801):
            with self.assertRaises(HTTPError) as ctx:
                self.request('/api/settings',dict(postcode='10001',interval=interval,notifications=True))
            self.assertEqual(ctx.exception.code,400)

    def test_pro_switch_and_no_auto_call(self):
        old=self.request('/api/collector/task')['task']
        self.request('/api/settings',dict(model='pro-test',postcode='10001',interval=30,notifications=True))
        task=self.request('/api/collector/task')['task']
        self.assertEqual(task['variant']['model'],'iPhone 18 Pro')
        with self.assertRaises(HTTPError):
            self.request('/api/collector/result',dict(id=old['id'],error='stale'))
        rows=[dict(store_id=sid,store=name,distance_km=5,status='available',message='Available Tomorrow') for sid,name in FIXTURE_STORES.items()]
        self.request('/api/collector/result',dict(id=task['id'],stores=rows))
        self.assertIsNone(self.request('/api/collector/task')['task'])
        self.mock_notify.assert_called_once()
        self.mock_phone.assert_not_called()
        self.assertEqual(len(server.STATE['results']),1)

    def test_duo_phone_aggregated_once_per_cycle(self):
        for i in range(8):
            task=self.request('/api/collector/task')['task']
            rows=[dict(store_id=sid,store=name,distance_km=5,status='available',message='Available Tomorrow') for sid,name in FIXTURE_STORES.items()]
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
        rows=[dict(store_id=sid,store=name,distance_km=5,status='available' if sid=='R250' else 'unavailable',message='Available today' if sid=='R250' else 'Currently unavailable') for sid,name in FIXTURE_STORES.items()]
        self.request('/api/collector/result',dict(id=task['id'],stores=rows))
        self.mock_notify.assert_called_once()
        self.assertIn('Fixture West 14th Street',self.mock_notify.call_args.args[0])
        server.STATE.update(running=False,queue=[],next_check=0)
        repeated=self.request('/api/collector/task')['task']
        self.request('/api/collector/result',dict(id=repeated['id'],stores=rows))
        self.mock_notify.assert_called_once()

    def test_failed_refresh_keeps_stores_visible_as_unknown(self):
        task=self.request('/api/collector/task')['task']
        rows=[dict(store_id='R077',store='Fixture Portland',status='available',message='Available today',distance_km=0.5)]
        self.request('/api/collector/result',dict(id=task['id'],stores=rows))
        server.STATE.update(running=False,queue=[],next_check=0)
        task=self.request('/api/collector/task')['task']
        self.request('/api/collector/result',dict(id=task['id'],error='HTTP 541'))
        self.assertEqual(self.request('/api/state')['stores'],{'R077':'Fixture Portland'})
        result=server.STATE['results'][task['variant']['id']]
        self.assertEqual(result['error'],'HTTP 541')
        self.assertEqual(result['stores'][0]['distance_km'],0.5)

    def test_pause_rejects_inflight_result_immediately(self):
        task=self.request('/api/collector/task')['task']
        self.request('/api/pause',{})
        with self.assertRaises(HTTPError) as ctx:
            self.request('/api/collector/result',dict(id=task['id'],error='late response'))
        self.assertEqual(ctx.exception.code,409)
        self.assertIsNone(server.STATE['task'])

    def test_large_dynamic_store_list_and_malformed_message(self):
        task=self.request('/api/collector/task')['task']
        rows=[dict(store_id='R'+str(i),store='Fixture Store '+str(i),status='unavailable',message='Currently unavailable'+' '*200,distance_km=i) for i in range(20)]
        self.request('/api/collector/result',dict(id=task['id'],stores=rows))
        self.assertEqual(len(server.display_stores()),20)
        task=self.request('/api/collector/task')['task']
        del rows[0]['message']
        with self.assertRaises(HTTPError) as ctx:
            self.request('/api/collector/result',dict(id=task['id'],stores=rows))
        self.assertEqual(ctx.exception.code,400)

    def test_radius_boundary_filters_before_persistence_and_alerts(self):
        task=self.request('/api/collector/task')['task']
        self.assertEqual(task['max_distance_km'],50)
        self.assertEqual(task['scope_version'],3)
        rows=[dict(store_id='R'+str(i),store=name,distance_km=distance,status='available',message='Available Today')
              for i,(name,distance) in enumerate([('Near',0),('Boundary',50),('Outside',50.00001),('Far',200)])]
        self.request('/api/collector/result',dict(id=task['id'],stores=rows))
        result=server.STATE['results'][task['variant']['id']]
        self.assertEqual([row['store'] for row in result['stores']],['Near','Boundary'])
        self.assertEqual(result['excluded_store_count'],2)
        self.mock_notify.assert_called_once()
        self.assertNotIn('Outside',self.mock_notify.call_args.args[0])
        self.assertNotIn('Far',str(server.PENDING_PHONE))
        self.assertEqual(len([e for e in server.STATE['events'] if e['kind']=='stock']),2)

    def test_distant_only_cycle_never_notifies_or_calls(self):
        for _ in range(8):
            task=self.request('/api/collector/task')['task']
            rows=[dict(store_id='R999',store='Far available',distance_km=51,status='available',message='Available Today')]
            self.request('/api/collector/result',dict(id=task['id'],stores=rows))
        self.request('/api/collector/task')
        self.mock_notify.assert_not_called()
        self.mock_phone.assert_not_called()
        self.assertEqual(server.display_stores(),{})
        self.assertTrue(all(r['stores']==[] and r['checked'] and not r['error'] for r in server.STATE['results'].values()))
        self.assertFalse(any(e['kind']=='stock' for e in server.STATE['events']))

    def test_unknown_invalid_distance_and_old_protocol_fail_closed(self):
        task=self.request('/api/collector/task')['task']
        row=dict(store_id='R077',store='Unknown',status='available',message='Available Today')
        for invalid in (None,-1,True,'1',float('nan'),float('inf')):
            with self.assertRaises(HTTPError) as ctx:
                self.request('/api/collector/result',dict(id=task['id'],stores=[dict(row,distance_km=invalid)]))
            self.assertEqual(ctx.exception.code,400)
        with self.assertRaises(HTTPError):
            self.request('/api/collector/result',dict(id=task['id'],stores=[row]))
        with self.assertRaises(HTTPError):
            self.request('/api/collector/result',dict(id=task['id'],postcode='10001',scope_version=2,stores=[dict(row,distance_km=1)]))
        self.mock_notify.assert_not_called()
        self.assertEqual(server.PENDING_PHONE,[])
        self.assertEqual(server.display_stores(),{})

    def test_nearby_alert_excludes_far_store_and_is_deduplicated(self):
        rows=[dict(store_id='R077',store='Near available',distance_km=15,status='available',message='Available Today'),
              dict(store_id='R999',store='Far available',distance_km=190,status='available',message='Available Today')]
        for cycle in range(2):
            server.STATE.update(next_check=0)
            for _ in range(8):
                task=self.request('/api/collector/task')['task']
                self.request('/api/collector/result',dict(id=task['id'],stores=rows))
            self.request('/api/collector/task')
        self.assertEqual(self.mock_notify.call_count,8)
        self.mock_phone.assert_called_once()
        self.assertIn('Near available',self.mock_phone.call_args.args[0])
        self.assertNotIn('Far available',self.mock_phone.call_args.args[0])

if __name__=='__main__':unittest.main()
