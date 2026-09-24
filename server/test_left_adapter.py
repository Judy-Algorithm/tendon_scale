import hashlib
import os
import unittest
from pathlib import Path
import numpy as np
import opensim as o
from personalize import prepare,load_raw,matrix,vec,FIT_COORDS,joint_point
from left_adapter import repair_left_geometry,LEFT_BASE_HASH,LEFT_ADAPTER
from path_repairs import repair_wrap_domains

@unittest.skipUnless(os.environ.get('TENDON_RUNTIME'),'Requires private server assets')
class LeftAdapterTests(unittest.TestCase):
    def test_sample02_observed_small_finger_is_applied_and_uncertainty_kept(self):
        root,base=self.paths()
        model,state,plan,report,points,valid,times=prepare(base,root/'cache/sample-02-raw.npz')
        rows={r['id']:r for r in report['scaledSegments']}
        proximal=rows['5_proximal'];tip=rows['5_distal_tip']
        self.assertEqual(proximal['scaleMethod'],'oblique_span_uniform_template')
        self.assertAlmostEqual(proximal['resultLengthM'],.02098500801634835,places=9)
        self.assertEqual(tip['measurementStatus'],'review')
        self.assertEqual(tip['reason'],'conflicting_stable_windows')
        self.assertEqual(tip['status'],'estimated')
        self.assertAlmostEqual(tip['resultLengthM'],tip['lengthM'],places=9)
        self.assertGreater(abs(tip['resultLengthM']-tip['baseLengthM']),.001)
        # All attached geometry/markers are transformed once, not just UI values.
        np.testing.assert_allclose(vec(model.getMarkerSet().get('personal_tip_20').get_location()),
            np.array(next(t for t in plan['landmarkEstimates']['tips'] if t['marker']=='personal_tip_20')['baseLocationLocalM'])*plan['bodyScaleXYZ']['5distph'],atol=1e-10)
        _,_,again,*_=prepare(base,root/'cache/sample-02-raw.npz',cached_plan=plan)
        self.assertEqual(again,plan)

    def paths(self):
        root=Path(os.environ['TENDON_RUNTIME'])
        return root,root/'base/Hand_Wrist_Model_LEFT_GlobalX180.osim'

    def test_source_side_and_scaling_are_independent(self):
        root,base=self.paths();raw=root/'cache/sample-raw.npz'
        x,v,t,meta=load_raw(raw,'left');r,_,_,_=load_raw(raw,'right')
        with np.load(raw,allow_pickle=False) as data:
            np.testing.assert_allclose(x,data['joints_world_raw'][:,0],equal_nan=True)
        self.assertGreater(np.nanmedian(np.linalg.norm(x-r,axis=-1)),.02)
        model,state,plan,report,*_=prepare(base,raw)
        self.assertEqual(plan['hand'],'left');self.assertEqual(plan['adapter'],LEFT_ADAPTER)
        self.assertEqual(report['modelSide'],'left')
        for row in report['scaledSegments']:
            if row['status'] in ('scaled','estimated'):self.assertLess(abs(row['lengthM']-row['resultLengthM']),1e-6)
        for tip in plan['landmarkEstimates']['tips']:
            self.assertGreater(tip['baseLocationLocalM'][1],0)
            xyz=plan['bodyScaleXYZ'].get(tip['body'],[1,1,1])
            np.testing.assert_allclose(vec(model.getMarkerSet().get(tip['marker']).get_location()),np.array(tip['baseLocationLocalM'])*xyz,atol=1e-10)
        self.assertEqual(hashlib.sha256(base.read_bytes()).hexdigest(),LEFT_BASE_HASH)
        _,_,again,*_=prepare(base,raw,cached_plan=plan);self.assertEqual(plan,again)

    def test_left_kinematics_meshes_and_attachments_obey_same_reflection(self):
        root,base=self.paths();right=o.Model(str(root/'base/Hand_Wrist_Model_for_development.osim'));left=o.Model(str(base))
        repair_left_geometry(left);repair_wrap_domains(right);repair_wrap_domains(left)
        a=right.initSystem();b=left.initSystem();P=np.diag([1.,1.,-1.,1.]);S=np.diag([1.,-1.,1.,1.])
        reference={c.getName():c.getValue(a) for c in right.getCoordinateSet()}
        for phase in (0.,.15,.35):
            for c in right.getCoordinateSet():
                if c.isDependent(a):continue
                value=reference[c.getName()]
                if c.getName() in FIT_COORDS+['flexion','deviation']:value=(1-phase)*value+phase*(c.getRangeMin()+c.getRangeMax())/2
                if c.getName() in ('flexion','deviation'):value=reference[c.getName()]+phase*(c.getRangeMax()-reference[c.getName()])*.5
                c.setValue(a,value,False);left.getCoordinateSet().get(c.getName()).setValue(b,value,False)
            right.assemble(a);left.assemble(b);right.realizePosition(a);left.realizePosition(b)
            for rb in right.getBodySet():
                lb=left.getBodySet().get(rb.getName())
                np.testing.assert_allclose(matrix(lb.getTransformInGround(b)),P@matrix(rb.getTransformInGround(a))@S,atol=1e-9)
                for i in range(rb.getPropertyByName('attached_geometry').size()):
                    np.testing.assert_allclose(vec(lb.get_attached_geometry(i).get_scale_factors()),[1,-1,1])
            for rm in right.getMuscles():
                lm=left.getMuscles().get(rm.getName());rp=rm.getGeometryPath().getPathPointSet();lp=lm.getGeometryPath().getPathPointSet()
                for j in range(rp.getSize()):
                    np.testing.assert_allclose(vec(lp.get(j).getLocationInGround(b)),P[:3,:3]@vec(rp.get(j).getLocationInGround(a)),atol=1e-9)
                self.assertLess(abs(lm.getGeometryPath().getLength(b)-rm.getGeometryPath().getLength(a)),.001,rm.getName())

if __name__=='__main__':unittest.main()
