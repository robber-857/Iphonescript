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
        self.assertEqual(len(STORES),7)
        self.assertNotIn('R483',STORES)

if __name__=='__main__':
    unittest.main()
