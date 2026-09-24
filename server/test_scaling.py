import unittest
import numpy as np
from scaling_core import observations, measure_span, axial_factor, segment_scale, rigid_alignment


class ScalingTests(unittest.TestCase):
    def test_units_and_invalid(self):
        p = np.zeros((50, 2, 3)); p[:, 1, 1] = 30
        p[0, 1] = np.nan
        normalized, valid = observations(p, np.ones((50, 2), bool), 'mm')
        self.assertFalse(valid[0, 1])
        self.assertEqual(measure_span(normalized, valid, 0, 1)['lengthM'], .03)
        with self.assertRaises(ValueError):
            observations(p, valid, 'unknown')
        self.assertEqual(p[1, 1, 1], 30)

    def test_outliers_and_interpolation(self):
        p = np.zeros((50, 2, 3)); p[:, 1, 1] = .03
        p[-1, 1, 1] = .08
        interpolated = np.zeros((50, 2), bool); interpolated[0] = True
        p, v = observations(p, np.ones((50, 2), bool), 'm', interpolated)
        result = measure_span(p, v, 0, 1)
        self.assertEqual(result['count'], 48)
        self.assertEqual(result['lengthM'], .03)

    def test_missing_is_not_zero_length(self):
        result = measure_span(np.zeros((20, 2, 3)), np.zeros((20, 2), bool), 0, 1)
        self.assertEqual(result['status'], 'insufficient_data')
        self.assertNotIn('lengthM', result)

    def test_axial_scale_preserves_transverse_span(self):
        delta = np.array([.005, -.04, .006])
        factor = axial_factor(delta, .03)
        self.assertAlmostEqual(np.linalg.norm(delta*[1, factor, 1]), .03)
        self.assertNotAlmostEqual(factor, .03/np.linalg.norm(delta), places=4)
        with self.assertRaises(ValueError):
            axial_factor(delta, .001)

    def test_rigid_invariance_and_no_reflection(self):
        rng = np.random.default_rng(42)
        p = rng.normal(size=(10, 3))
        rotation = np.array([[0,-1,0],[1,0,0],[0,0,1.]])
        q = p@rotation.T + [1,2,3]
        r, t = rigid_alignment(p, q)
        np.testing.assert_allclose(p@r.T+t, q, atol=1e-12)
        self.assertAlmostEqual(np.linalg.det(r), 1)

    def test_oblique_observed_span_uses_shape_preserving_scale(self):
        d=np.array([-.0125,.0335,.0043]); target=.02098500801634835
        with self.assertRaises(ValueError):axial_factor(d,target)
        result=segment_scale(d,target)
        self.assertEqual(result['scaleMethod'],'oblique_span_uniform_template')
        out=d*result['scaleXYZ']
        self.assertAlmostEqual(np.linalg.norm(out),target)
        np.testing.assert_allclose(out/np.linalg.norm(out),d/np.linalg.norm(d))
        self.assertEqual(result['crossSection'],'template_proportional_estimate')
        with self.assertRaises(ValueError):segment_scale(d,.001)

    def test_repeated_stable_windows_not_template_or_one_quiet_interval(self):
        t=np.arange(900)/30.;p=np.zeros((900,2,3));v=np.ones((900,2),bool)
        # Five quiet intervals agree; the other intervals have large alternating noise.
        p[:,1,1]=.02+np.where(np.arange(900)%2,.005,-.005)
        for start in (0,180,360,540,720):p[start:start+90,1,1]=.021
        r=measure_span(p,v,0,1,times=t)
        self.assertEqual(r['status'],'measured');self.assertEqual(r['measurementMethod'],'repeated_stable_windows')
        self.assertAlmostEqual(r['lengthM'],.021);self.assertGreaterEqual(r['stableWindowCount'],3)
        p[:,1,1]=.02+np.where(np.arange(900)%2,.005,-.005);p[:90,1,1]=.021
        self.assertEqual(measure_span(p,v,0,1,times=t)['status'],'review')

    def test_conflicting_stable_modes_are_not_cherry_picked(self):
        t=np.arange(900)/30.;p=np.zeros((900,2,3));p[:,1,1]=np.where(np.arange(900)//90%2,.025,.018)
        r=measure_span(p,np.ones((900,2),bool),0,1,times=t)
        self.assertEqual(r['status'],'review');self.assertEqual(r['reason'],'conflicting_stable_windows')


if __name__ == '__main__':
    unittest.main()
