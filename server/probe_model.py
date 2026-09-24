"""Read-only model adapter diagnostics."""
import sys
import opensim as o

o.Logger.setLevelString('error')
m = o.Model(sys.argv[1])
s = m.initSystem()
print('Version', o.GetVersionAndDate())
for i in range(m.getJointSet().getSize()):
    j = m.getJointSet().get(i)
    print(j.getName(), j.getParentFrame().getAbsolutePathString(),
          j.getChildFrame().getAbsolutePathString(),
          j.getParentFrame().getPositionInGround(s))
print('Mesh', [x for x in dir(o.Mesh) if 'Frame' in x or 'scale' in x])
print('Path', m.getMuscles().get(0).getGeometryPath().getCurrentPath(s).getSize())
print('Scales', [x for x in dir(o.Scale) if 'set' in x and ('cale' in x or 'egment' in x)])
print('Transforms', [x for x in dir(o.Transform) if x in ('R', 'p', 'toMat44')])
