"""Explicit template proxies for observed surface tips, not anatomical calibration."""
import hashlib
import numpy as np
import opensim as o

TIPS = {4:'distal_thumb',8:'2distph',12:'3distph',16:'4distph',20:'5distph'}
SURFACE_VERTEX_IDS = {4:744,8:320,12:443,16:554,20:671}
SOURCE_AUDIT = dict(
    auditedDate='2026-09-10',historicalProductionRevisionVerified=False,
    implementation='wilor-based-gt / WiLoR MANO wrapper; multiview DLT before temporal smoothing',
    files={
        'third_party/WiLoR/wilor/models/mano_wrapper.py':'a744e9db96fbd9b0f20618a9a1b56a707e21b544a9c3991b781ba1909ebb26c3',
        'smplx/vertex_ids.py':'1fa22bcbdb89eec7640224b70140a1e9404baf078fa8667f9e0118026b4276be',
        'wilor_gt/motion_capture_ground_truth/pipeline.py':'ef21275969a5a20760c8e1f91ee6256499c6e30dbfe2597a6ab97f15ee480921'})


def distal_cap_proxy(vertices,direction=-1):
    v = np.asarray(vertices, dtype=float)
    if v.ndim != 2 or v.shape[1] != 3 or len(v)<10 or not np.isfinite(v).all():
        raise ValueError('Invalid template mesh')
    # Reviewed local distal direction for these five supplied meshes is -Y.
    # Average the terminal cap, not a single potentially irregular extremal vertex.
    if direction not in (-1,1):raise ValueError('Unknown distal direction')
    cap = v[v[:,1]*direction >= np.quantile(v[:,1]*direction,.98)]
    point = cap.mean(axis=0)
    if point[1]*direction<=0 or not .005<np.linalg.norm(point)<.06:
        raise ValueError('Unexpected distal mesh orientation or dimensions')
    return point


def add_tip_proxies(model, state, base, mesh_reader, vec, matrix, direction=-1):
    rows = []
    for index, owner in TIPS.items():
        body=model.getBodySet().get(owner)
        vertices=[];sources=[]
        for i in range(body.getPropertyByName('attached_geometry').size()):
            mesh=o.Mesh.safeDownCast(body.get_attached_geometry(i))
            if mesh is None:continue
            file=base.parent/'Geometry'/mesh.get_mesh_file()
            points,_=mesh_reader(file)
            points=points*vec(mesh.get_scale_factors())
            t=matrix(mesh.getFrame().findTransformBetween(state,body))
            vertices.extend(points@t[:3,:3].T+t[:3,3])
            sources.append(dict(file=file.name,sha256=hashlib.sha256(file.read_bytes()).hexdigest()))
        location=distal_cap_proxy(vertices,direction)
        marker_name=f'personal_tip_{index}'
        rows.append(dict(sourceIndex=index,body=owner,marker=marker_name,baseLocationLocalM=location.tolist(),
                         sourceSurfaceVertexIndex=SURFACE_VERTEX_IDS[index],
                         method=('distal_cap_negative_y_2percent_mean' if direction==-1 else 'distal_cap_positive_y_2percent_mean'),geometry=sources,
                         status='model_estimate',softTissueOffsetM=0.,
                         limitation='Bone-cap proxy for a skin-surface point; fitted scale absorbs unmeasured soft tissue.'))
    # Adding a component invalidates the System: finish all geometry queries first.
    for row in rows:
        model.addMarker(o.Marker(row['marker'],model.getBodySet().get(row['body']),o.Vec3(*row['baseLocationLocalM'])))
    return rows
