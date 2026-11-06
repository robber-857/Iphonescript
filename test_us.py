import copy, json, threading, unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from unittest.mock import patch
import server
from monitor import VARIANTS, PRO_VARIANTS

class USTests(unittest.TestCase):
 def setUp(self):
  self.original=copy.deepcopy(server.STATE)
 def tearDown(self):
  server.STATE.clear();server.STATE.update(self.original)
  server.PENDING_PHONE.clear()
 def test_urls(self):
  for v in VARIANTS+PRO_VARIANTS:
   self.assertTrue(v['url'].startswith('https://www.apple.com/shop/'))
 def test_zip_and_inventory(self):
  import io
  def call(path,body):
   handler=object.__new__(server.Handler)
   raw=json.dumps(body).encode()
   handler.path=path
   handler.headers={'Host':'127.0.0.1:8766','X-Duo-Token':server.TOKEN,'Content-Length':str(len(raw))}
   handler.rfile=io.BytesIO(raw)
   result=[]
   handler.send=lambda code,body:result.append((code,body))
   handler.do_POST()
   code,response=result[0]
   if code>=400:raise HTTPError(path,code,str(response),{},None)
   return response
  try:
   with patch.object(server,'save'),patch.object(server,'notify'):
    for zip in ['10001','02108','90210']:
     call('/api/settings',dict(interval=300,notifications=False,postcode=zip))
     self.assertEqual(server.STATE['postcode'],zip)
    for zip in ['2000','123456','ABCDE']:
     with self.assertRaises(HTTPError):
      call('/api/settings',dict(interval=300,notifications=False,postcode=zip))
    server.STATE['task']=dict(id='us',postcode='90210',variant=VARIANTS[0])
    rows=[dict(store_id='R999',store='Test US Store',status='available',message='Available today')]
    call('/api/collector/result',dict(id='us',postcode='90210',scope_version=2,stores=rows))
    self.assertEqual(server.display_stores(),{'R999':'Test US Store'})
  finally:
   server.PENDING_PHONE.clear()

if __name__=='__main__':unittest.main()
