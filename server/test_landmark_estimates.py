import unittest
import numpy as np
from landmark_estimates import distal_cap_proxy, SURFACE_VERTEX_IDS


class LandmarkEstimates(unittest.TestCase):
    def test_proxy_is_deterministic_and_equivariant_to_positive_uniform_scale(self):
        y=np.linspace(-.02,0,1001)
        mesh=np.column_stack([.001*np.cos(y*1000),y,.001*np.sin(y*1000)])
        point=distal_cap_proxy(mesh)
        np.testing.assert_allclose(distal_cap_proxy(mesh[::-1]),point,atol=1e-14)
        np.testing.assert_allclose(distal_cap_proxy(mesh*1.4),point*1.4,atol=1e-14)
        self.assertEqual(SURFACE_VERTEX_IDS,{4:744,8:320,12:443,16:554,20:671})

    def test_invalid_geometry_cannot_silently_define_a_tip(self):
        for mesh in (np.zeros((9,3)),np.full((20,3),np.nan),np.ones((20,3))*.01):
            with self.assertRaises(ValueError):distal_cap_proxy(mesh)


if __name__=='__main__':unittest.main()
