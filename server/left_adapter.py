"""Mirror consistency repair for the user's immutable left-hand OpenSim model.

Joint axes, offsets, fixed muscle points and wrap poses are already reflected;
meshes, moving-point functions and wrap half-spaces need the reviewed repairs.
This is NOT a reflection of fitted right data.
"""
import opensim as o

LEFT_BASE_HASH='45c45732788afd4fcc78b89c97cf7a5da51de82dcb735d480459ee4e8770207b'
LEFT_ADAPTER='arms-left-landmarks-1'

def repair_left_geometry(model):
    repairs=[]
    for body in model.getBodySet():
        for i in range(body.getPropertyByName('attached_geometry').size()):
            mesh=o.Mesh.safeDownCast(body.get_attached_geometry(i))
            if mesh is None:continue
            old=[mesh.get_scale_factors().get(j) for j in range(3)]
            if old!=[1.,1.,1.]:raise ValueError('Left source mesh scaling changed; re-audit required')
            mesh.set_scale_factors(o.Vec3(1.,-1.,1.))
            repairs.append(dict(body=body.getName(),mesh=mesh.get_mesh_file(),localReflection=[1,-1,1]))
    # This missing thorax asset belongs to Ground, not to the displayed hand.
    # Global X180 followed by the source local Y reflection equals global Z reflection.
    ground=model.getGround()
    for i in range(ground.getPropertyByName('attached_geometry').size()):
        mesh=o.Mesh.safeDownCast(ground.get_attached_geometry(i))
        if mesh is not None and mesh.get_mesh_file()=='thorax_GlobalX180.vtp':
            mesh.set_mesh_file('thorax.vtp');mesh.set_scale_factors(o.Vec3(1.,1.,-1.))
    moving=[]
    for muscle in model.getMuscles():
        for point in muscle.getGeometryPath().getPathPointSet():
            mp=o.MovingPathPoint.safeDownCast(point)
            if mp is None:continue
            if mp.getName() not in ('APL-P6','FPL-P5'):raise ValueError('Unexpected moving path point')
            function=o.SimmSpline.safeDownCast(mp.upd_y_location())
            if function is None:raise ValueError('Unreviewed moving-point function')
            for i in range(function.getNumberOfPoints()):function.setY(i,-function.getY(i))
            moving.append(mp.getName())
    if sorted(moving)!=['APL-P6','FPL-P5']:raise ValueError('Left moving-point topology changed')
    # Restore the audited development-template half-space restrictions, reflected
    # in each wrap object's Y coordinate. The supplied left file changed all to all.
    source_quadrants={'Elbow_PT_ECRL':'x','EIP':'z','PL':'-z','FDS':'-z','FDP':'y','EDM':'-z','FPL':'-z',
        'IPthumb':'-x','2ndmcp_FDSI':'y','2ndmcp_FDPI':'y','5thmcp':'-x','2ndpm_FDPI':'y',
        '2ndpm_extI':'-y','Secondpm':'x','2ndmd_extI':'-y','Secondmd':'x','Thirdmd':'x','Fourthmd':'x','Fifthmd':'x'}
    quadrants=[]
    for body in model.getBodySet():
        for wrap in body.getWrapObjectSet():
            if wrap.getName() not in source_quadrants:continue
            source=source_quadrants[wrap.getName()]
            target={'y':'-y','-y':'y'}.get(source,source)
            wrap.set_quadrant(target)
            quadrants.append(dict(wrap=wrap.getName(),quadrant=target))
    if len(quadrants)!=len(source_quadrants):raise ValueError('Left wrap topology changed')
    return dict(status='runtime_mirror_repair',bodyMeshes=repairs,sourceXMLUnchanged=True,
                movingPointsYReflected=moving,wrapQuadrantsRestored=quadrants,
                note='Left kinematics retained; mesh and moving-point Y reflection repaired; template wrap half-spaces restored under reflection')
