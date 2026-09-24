import unittest
import numpy as np
from palm_scaling import estimate_palm


class PalmTests(unittest.TestCase):
    def fixture(self):
        ref=np.array([[-.03,0,0],[-.01,.006,0],[.01,.004,0],[.03,-.008,0]])
        points=np.zeros((180,21,3));points[:,[5,9,13,17]]=ref
        return ref,points,np.ones((180,21),bool),np.arange(180)/30

    def test_rigid_motion_does_not_scale_palm(self):
        ref,p,v,t=self.fixture()
        for i in range(len(p)):
            a=i*.015;r=np.array([[np.cos(a),-np.sin(a),0],[np.sin(a),np.cos(a),0],[0,0,1]])
            p[i]=p[i]@r.T+[i*.001,0,.2]
        result=estimate_palm(p,v,t,ref)
        self.assertEqual(result['status'],'inferred')
        np.testing.assert_allclose(result['shiftsGroundM'],np.zeros((4,3)),atol=1e-12)

    def test_width_change_is_fixed_layout_not_bone_length(self):
        ref,p,v,t=self.fixture();p[:,:,0]*=.9
        result=estimate_palm(p,v,t,ref)
        self.assertEqual(result['status'],'inferred')
        self.assertGreater(np.linalg.norm(result['shiftsGroundM']),.001)
        np.testing.assert_allclose(np.mean(result['targetM'],axis=0),ref.mean(0),atol=1e-12)

    def test_missing_or_degenerate_returns_review(self):
        ref,p,v,t=self.fixture();v[:]=False
        self.assertEqual(estimate_palm(p,v,t,ref)['status'],'review')
        ref[:,1:]=0
        self.assertEqual(estimate_palm(p,v,t,ref)['reason'],'degenerate_model_palm')


if __name__=='__main__':unittest.main()
