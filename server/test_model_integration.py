"""Run on the server with TENDON_RUNTIME set; never writes the base or a model copy."""
import hashlib
import os
import unittest
from pathlib import Path
import numpy as np
from personalize import prepare, joint_point, LANDMARKS, vec, TIPS, FIT_COORDS, fit_clip


@unittest.skipUnless(os.environ.get('TENDON_RUNTIME'), 'Requires private server assets')
class ModelIntegration(unittest.TestCase):
    def test_distal_coordinates_fit_valid_points_and_keep_wrapped_paths_bounded(self):
        root=Path(os.environ['TENDON_RUNTIME'])
        model,state,plan,report,points,valid,times=prepare(root/'base/Hand_Wrist_Model_for_development.osim',root/'cache/sample-raw.npz')
        _,_,frames,motion=fit_clip(model,state,points,valid,times,end=30.6,stride=3)
        self.assertEqual(motion['observedIndices'],list(range(1,21)))
        self.assertLess(motion['pathExportMaxErrorMm'],1.)
        self.assertLess(motion['maxPathLengthM'],.6)
        self.assertLess(motion['rmseMedianMm'],7.)
        for name in ['ip_flexion']+[f'{i}md_flexion' for i in range(2,6)]:
            lo,hi=motion['coordinateRangesRad'][name]
            self.assertGreater(hi-lo,.001,name)
        for frame in frames:
            for index in frame.get('landmarkErrorsMm',{}):
                self.assertTrue(valid[frame['sourceFrame'],int(index)])
        self.assertLess(motion['distalObservationSupport']['ip_flexion']['observedFrames'],len(frames))

    def test_development_base_and_complete_coverage(self):
        root = Path(os.environ['TENDON_RUNTIME'])
        base=root/'base/Hand_Wrist_Model_for_development.osim'
        raw=root/'cache/sample-raw.npz'
        model,state,plan,report,*_=prepare(base,raw)
        self.assertEqual(len(report['allSegments']),19)
        self.assertEqual(report['baseModelName'],base.name)
        self.assertFalse(report['scaleComplete'])
        self.assertEqual([x['range'] for x in plan['pathWrapRepairs']],[[2,3],[5,6],[7,8]])
        self.assertEqual([x['wrapObject'] for x in plan['pathWrapRepairs']],['FDP','2ndmcp_FDPI','2ndpm_FDPI'])
        self.assertEqual(sum(r['status']=='estimated' for r in report['allSegments']),6)
        self.assertEqual(sum(r['status']=='scaled' for r in report['allSegments']),9)
        self.assertEqual(len(FIT_COORDS),20)
        for row in report['scaledSegments']:
            self.assertLess(abs(row['resultLengthM']-row['lengthM']),1e-6)
        for tip in plan['landmarkEstimates']['tips']:
            actual=vec(model.getMarkerSet().get(tip['marker']).get_location())
            expected=np.array(tip['baseLocationLocalM'])*plan['bodyScaleXYZ'][tip['body']]
            np.testing.assert_allclose(actual,expected,atol=1e-10)
            self.assertEqual(tip['status'],'model_estimate')
            self.assertEqual(len(tip['geometry'][0]['sha256']),64)
            body=model.getBodySet().get(tip['body'])
            for i in range(body.getPropertyByName('attached_geometry').size()):
                mesh=body.get_attached_geometry(i)
                np.testing.assert_allclose(vec(mesh.get_scale_factors()),plan['bodyScaleXYZ'][tip['body']],atol=1e-10)
        self.assertEqual(sum(r['status']=='awaiting_input' for r in report['allSegments']),4)
        self.assertLess(report['palmLayout']['maxPairErrorM'],.00005)
        for row in report['allSegments']:
            if row['status']=='awaiting_input':
                self.assertAlmostEqual(row['baseLengthM'],row['resultLengthM'],places=10)
        _,_,second,*_=prepare(base,raw,cached_plan=plan)
        self.assertEqual(plan,second)

    def test_dimensions_reproducibility_connections_and_fmax(self):
        root = Path(os.environ['TENDON_RUNTIME'])
        base = root/'base/HandModel_Personalized_20260804_Fmax_visible.osim'
        raw = root/'cache/sample-raw.npz'
        before = hashlib.sha256(base.read_bytes()).hexdigest()
        model, state, plan, report, *_ = prepare(base, raw)
        self.assertEqual(len(plan['bodyScaleY']), 15)
        for row in report['scaledSegments']:
            self.assertLess(abs(row['resultLengthM']-row['lengthM']), 1e-6)
        for name in LANDMARKS.values():
            j = model.getJointSet().get(name)
            self.assertLess(np.linalg.norm(vec(j.getParentFrame().getPositionInGround(state))-vec(j.getChildFrame().getPositionInGround(state))), 1e-8)
        self.assertEqual(len(report['muscleParameters']), 43)
        self.assertFalse(report['dynamicsReady'])
        # Each muscle remains a real OpenSim path with positive finite length.
        for muscle in model.getMuscles():
            length = muscle.getGeometryPath().getLength(state)
            self.assertTrue(np.isfinite(length) and length > 0)
        second, state2, plan2, *_ = prepare(base, raw, cached_plan=plan)
        self.assertEqual(plan, plan2)
        for index in set(LANDMARKS)|set(TIPS):
            np.testing.assert_allclose(joint_point(model,state,index),joint_point(second,state2,index),atol=1e-10)
        self.assertEqual(before, hashlib.sha256(base.read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()
