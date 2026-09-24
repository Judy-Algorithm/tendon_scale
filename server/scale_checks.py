"""Numerical scaling checks; these do not certify anatomy or collision clearance."""
import numpy as np
import opensim as o


def sample_paths(model, reference, samples=13):
    state=model.initSystem()
    independent=[c for c in model.getCoordinateSet() if not c.isDependent(state)]
    muscles=list(model.getMuscles())
    rows=[];nonfinite=[];jumps=[]
    def reset():
        for c in independent:c.setValue(state,reference[c.getName()],False)
    for coord in independent:
        lengths=[];arms=[]
        for value in np.linspace(coord.getRangeMin(),coord.getRangeMax(),samples):
            reset();coord.setValue(state,float(value),False);model.assemble(state);model.realizePosition(state)
            length=[];arm=[]
            for muscle in muscles:
                a=float(muscle.computeMomentArm(state,coord));l=float(muscle.getGeometryPath().getLength(state))
                if not np.isfinite(a) or not np.isfinite(l) or l<=0:
                    nonfinite.append(dict(coordinate=coord.getName(),muscle=muscle.getName(),value=float(value)))
                arm.append(a);length.append(l)
            lengths.append(length);arms.append(arm)
        lengths=np.array(lengths);arms=np.array(arms)
        for i,muscle in enumerate(muscles):
            if np.max(np.abs(np.diff(arms[:,i])))>.02:
                jumps.append(dict(coordinate=coord.getName(),muscle=muscle.getName(),momentArmJumpM=float(np.max(np.abs(np.diff(arms[:,i]))))))
        rows.append(dict(coordinate=coord.getName(),samples=samples,
                         minLengthM=float(np.min(lengths)),maxLengthM=float(np.max(lengths)),
                         maxAbsMomentArmM=float(np.max(np.abs(arms)))))
    reset();model.assemble(state);model.realizePosition(state)
    return state,dict(status='review' if nonfinite or jumps else 'pass',
                      samplesPerCoordinate=samples,coordinates=len(independent),muscles=len(muscles),
                      nonfinite=nonfinite,momentArmJumpWarnings=jumps,summary=rows,
                      collisionStatus='not_supported',anatomicalValidation='not_run',
                      scope='one coordinate at a time; jump threshold is an engineering warning, not a physiological criterion')
