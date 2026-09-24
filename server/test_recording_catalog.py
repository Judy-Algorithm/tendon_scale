import tempfile
import unittest
from pathlib import Path
from recording_catalog import validate_records,public_record

class CatalogTests(unittest.TestCase):
    def test_six_samples_are_explicit_unique_and_paths_are_not_public(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'cache').mkdir();records=[]
            for i in range(1,7):
                identifier=f'sample-{i:02d}';filename='sample-raw.npz' if i==1 else identifier+'-raw.npz'
                (root/'cache'/filename).touch()
                records.append(dict(id=identifier,rawFile=filename,hand='right',startS=30,endS=42,durationS=120,sourceHash=str(i)*64))
            result=validate_records(records,root)
            self.assertEqual(len(result),6)
            self.assertNotIn('rawFile',public_record(result['sample-02']))
            self.assertEqual(result['sample-06']['videoBase'],'/media/sample-06')
            for change in [dict(id='sample-07'),dict(rawFile='../secret'),dict(hand='left'),dict(sourceHash='1'*64),dict(endS=121)]:
                bad=[dict(r) for r in records];bad[1].update(change)
                with self.assertRaises(ValueError):validate_records(bad,root)

if __name__=='__main__':unittest.main()
