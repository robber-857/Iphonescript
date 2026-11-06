import unittest
from monitor import classify, stock_changes, VARIANTS, STORES

class StockTests(unittest.TestCase):
    def test_unavailable_is_not_positive_substring(self):
        self.assertEqual(classify(True,'Currently unavailable\nIn-Store Pickup'),'unavailable')
        self.assertEqual(classify(False,'Currently unavailable'),'unavailable')

    def test_positive_requires_enabled_option(self):
        self.assertEqual(classify(False,'Available today'),'available')
        self.assertEqual(classify(True,'Available today'),'unknown')
        self.assertEqual(classify(False,''),'unknown')

    def test_restock_and_deduplication(self):
        row=dict(store_id='R238',status='available')
        self.assertEqual(stock_changes([], [row]),[row])
        self.assertEqual(stock_changes([row],[row]),[])
        self.assertEqual(stock_changes([dict(store_id='R238',status='unavailable')],[row]),[row])

    def test_scope(self):
        self.assertEqual(len(VARIANTS),8)
        self.assertEqual(len({v['id'] for v in VARIANTS}),8)
        self.assertEqual(STORES,{})
        self.assertNotIn('R483',STORES)

    def test_scope_migration_removes_far_and_unknown_without_replaying_alerts(self):
        from monitor import migrate_monitoring_scope
        state={'results':{'duo':{'stores':[{'store_id':'R1','distance_km':1},{'store_id':'R2','distance_km':51},{'store_id':'R3'}]}},
               'events':[{'kind':'stock','message':'old far alert'},{'kind':'info','message':'keep'}]}
        migrate_monitoring_scope(state)
        self.assertEqual(state['results']['duo']['stores'],[{'store_id':'R1','distance_km':1}])
        self.assertIn('距离未确认',state['results']['duo']['error'])
        self.assertEqual(state['events'],[{'kind':'info','message':'keep'}])
        self.assertEqual(state['max_distance_km'],50)
        state['events'].append({'kind':'stock','message':'new nearby alert'})
        migrate_monitoring_scope(state)
        self.assertEqual(len(state['events']),2)

if __name__=='__main__':
    unittest.main()
