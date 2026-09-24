import tempfile
import unittest
from pathlib import Path
from all_catalog import inventory,public_record,LEGACY_NAMES,checked_source

class AllCatalogTests(unittest.TestCase):
    def test_inventory_is_stable_complete_and_does_not_read_rrd_contents(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);data=root/'dt=2026-09-01'/'device'/'rrd_data';data.mkdir(parents=True)
            for name in ['example-a.rrd','example-b.rrd']:(data/name).touch()
            first=inventory(root)
            self.assertEqual(len(first),2);self.assertTrue(all(k.startswith('record-') for k in first))
            new=next(r for r in first.values() if not r['legacy'])
            self.assertTrue(new['id'].startswith('record-'))
            self.assertNotIn('sourcePath',public_record(new))
            self.assertNotIn('sourceMtimeNs',public_record(new))
            (data/'another.rrd').touch()
            self.assertEqual(inventory(root)[new['id']],new)
            with self.assertRaises(ValueError):checked_source(new)

if __name__=='__main__':unittest.main()
