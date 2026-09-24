"""In-memory, directly bound adapters for the user's right and left OpenSim models.

No atlas, SHM model, imputation, or per-subject .osim.
Nine joint spans plus six explicitly labelled template-based estimates.
"""
import argparse
import hashlib
import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import opensim as o
from scipy.optimize import least_squares
from scipy.spatial.transform import Rotation

from scaling_core import observations, measure_span, segment_scale, rigid_alignment
from palm_scaling import estimate_palm, pair_lengths
from scale_checks import sample_paths
from path_repairs import repair_wrap_domains
from landmark_estimates import TIPS, SOURCE_AUDIT, add_tip_proxies
from left_adapter import LEFT_BASE_HASH,LEFT_ADAPTER,repair_left_geometry

ADAPTER_VERSION = 'arms-right-landmarks-2'
EXPECTED_BASE_HASH = '60674e6267df5071e029e052dc28c8f78610ebee205ab167dece2eb261c05885'
DEVELOPMENT_BASE_HASH = '9a88909ca27da9397abe22599e51ae9699162bdf274f65d2a83d7b02793b24cc'
LANDMARKS = {1: 'CMC1b', 2: 'MCP', 3: 'IP'}
SEGMENTS = [('thumb_proximal', '拇指近节', 'proximal_thumb', 2, 3)]
for digit, first, chinese in [(2, 5, '食指'), (3, 9, '中指'), (4, 13, '无名指'), (5, 17, '小指')]:
    LANDMARKS.update({first: f'_{digit}MCP', first+1: f'_{digit}prox-midph_b', first+2: f'_{digit}mid-distph'})
    SEGMENTS.extend([(f'{digit}_proximal', chinese+'近节', f'{digit}proxph', first, first+1),
                     (f'{digit}_middle', chinese+'中节', f'{digit}midph', first+1, first+2)])
FIT_COORDS = ['cmc_flexion', 'cmc_abduction', 'mp_flexion'] + [f'{i}{suffix}' for i in range(2, 6) for suffix in ('mcp_abduction', 'mcp_flexion', 'pm_flexion')]
FIT_COORDS += ['ip_flexion']+[f'{i}md_flexion' for i in range(2,6)]
# Humerus must stay: several displayed muscle origins are attached to it.
EXCLUDED_BODIES = {'clavicle', 'scapula'}


def vec(v):
    return np.array([v.get(i) for i in range(3)])


def matrix(transform):
    result = np.eye(4)
    result[:3, :3] = [[transform.R().get(i, j) for j in range(3)] for i in range(3)]
    result[:3, 3] = vec(transform.p())
    return result


def joint_point(model, state, index):
    if index in TIPS:
        return vec(model.getMarkerSet().get(f'personal_tip_{index}').getLocationInGround(state))
    return vec(model.getJointSet().get(LANDMARKS[index]).getChildFrame().getPositionInGround(state))


def mesh_data(filename):
    root = ET.parse(filename).getroot()
    points = root.find('.//Points/DataArray')
    connection = root.find('.//Polys/DataArray[@Name="connectivity"]')
    offsets = root.find('.//Polys/DataArray[@Name="offsets"]')
    if any(x is None or x.get('format') != 'ascii' for x in (points, connection, offsets)):
        raise ValueError('This adapter requires the supplied ASCII VTP geometry')
    vertices = np.fromstring(points.text, sep=' ').reshape(-1, 3)
    indices = np.fromstring(connection.text, sep=' ', dtype=np.int32)
    ends = np.fromstring(offsets.text, sep=' ', dtype=np.int32)
    faces, start = [], 0
    for end in ends:
        polygon = indices[start:end]
        for j in range(1, len(polygon)-1):
            faces.extend([int(polygon[0]), int(polygon[j]), int(polygon[j+1])])
        start = end
    return vertices, faces


def load_raw(path, hand='right'):
    if hand not in ('left','right'):
        raise ValueError('Explicit left or right hand required')
    with np.load(path, allow_pickle=False) as data:
        meta = json.loads(str(data['metadata']))
        if meta['sourceKind'] != 'raw_reconstructed_3d' or meta['pointField'] != 'joints_world_raw':
            raise ValueError('Only original reconstructed observations accepted')
        side = meta['handOrder'].index(hand)
        points, valid = observations(data['joints_world_raw'][:, side],
                                    data['valid_joints'][:, side] & data['valid'][:, side, None], meta['lengthUnit'])
        ns = data['capture_timestamp_ns'].astype(np.int64)
    if np.any(np.diff(ns) <= 0):
        raise ValueError('Timestamps must be strictly increasing')
    return points, valid, (ns - ns[0]).astype(float)*1e-9, meta


def prepare(base, raw, cached_plan=None):
    o.Logger.setLevelString('error')
    base_hash = hashlib.sha256(base.read_bytes()).hexdigest()
    if base_hash not in (EXPECTED_BASE_HASH, DEVELOPMENT_BASE_HASH,LEFT_BASE_HASH):
        raise ValueError('Base model changed; revalidate anatomical bindings before using this adapter')
    hand='left' if base_hash==LEFT_BASE_HASH else 'right'
    points, valid, times, meta = load_raw(raw,hand)
    model = o.Model(str(base))
    side_repair=repair_left_geometry(model) if hand=='left' else None
    state = model.initSystem()
    original_parameters = {m.getName(): (m.getMaxIsometricForce(), m.getOptimalFiberLength(), m.getTendonSlackLength()) for m in model.getMuscles()}
    original_paths = {m.getName(): m.getGeometryPath().getLength(state) for m in model.getMuscles()}
    reference = {c.getName(): c.getValue(state) for c in model.getCoordinateSet()}
    wrap_repairs = repair_wrap_domains(model)
    tip_proxies = add_tip_proxies(model,state,base,mesh_data,vec,matrix,1 if hand=='left' else -1)
    state = model.initSystem()
    rows, factors, scale_xyz = [], {}, {}
    for name, label, owner, a, b in SEGMENTS:
        body = model.getBodySet().get(owner)
        first = model.getJointSet().get(LANDMARKS[a]).getChildFrame()
        last = model.getJointSet().get(LANDMARKS[b]).getParentFrame()
        start = vec(first.findStationLocationInAnotherFrame(state, o.Vec3(0), body))
        end = vec(last.findStationLocationInAnotherFrame(state, o.Vec3(0), body))
        measured = measure_span(points, valid, a, b, times=times)
        accepted = measured.pop('acceptedFrames', [])
        measured['acceptedFramesHash'] = hashlib.sha256(np.asarray(accepted, dtype='<i8').tobytes()).hexdigest()
        row = dict(id=name, label=label, body=owner, observedIndices=[a, b],
                   measurementKind='joint_span', longAxisLocal=[0, 1 if hand=='left' else -1, 0],
                   originLocal=start.tolist(), modelDeltaLocal=(end-start).tolist(),
                   segmentDirectionLocal=((end-start)/np.linalg.norm(end-start)).tolist(),
                   baseLengthM=float(np.linalg.norm(end-start)), **measured)
        if np.linalg.norm(start) > 1e-8:
            raise ValueError(f'{owner}: nonzero scale origin requires explicit adapter support')
        row['measurementStatus'] = measured['status']
        if measured['status'] in ('measured','review') and 'lengthM' in measured:
            try:
                row.update(segment_scale(end-start, measured['lengthM']))
                row['scaleY'] = row['scaleXYZ'][1]
                row['status'] = 'scaled'
                factors[owner] = row['scaleY']
                scale_xyz[owner] = row['scaleXYZ']
            except ValueError as error:
                row.update(status='review', reason=str(error))
        rows.append(row)
    for digit, tip, label in [(1,4,'拇指'),(2,8,'食指'),(3,12,'中指'),(4,16,'无名指'),(5,20,'小指')]:
        a,b=tip-1,tip
        measured=measure_span(points,valid,a,b,times=times)
        accepted=measured.pop('acceptedFrames',[])
        base_length=float(np.linalg.norm(joint_point(model,state,b)-joint_point(model,state,a)))
        row=dict(id=f'{digit}_distal_tip',label=label+'远节至指尖',body=TIPS[tip],
                 observedIndices=[a,b],measurementKind='surface_tip_proxy_span',baseLengthM=base_length,
                 estimateMethod='template_shape_preserved_uniform',status='insufficient_data',**{k:v for k,v in measured.items() if k!='status'})
        row['acceptedFramesHash']=hashlib.sha256(np.asarray(accepted,dtype='<i8').tobytes()).hexdigest()
        row['measurementStatus']=measured['status']
        if measured['status'] in ('measured','review') and 'lengthM' in measured:
            factor=measured['lengthM']/base_length
            if not .5<=factor<=1.8:raise ValueError('Tip proxy scale outside engineering bounds')
            row.update(status='estimated',scaleY=factor,scaleXYZ=[factor]*3)
            factors[TIPS[tip]]=factor;scale_xyz[TIPS[tip]]=[factor]*3
        else:row['status']=measured['status']
        rows.append(row)
    measured=measure_span(points,valid,1,2,times=times)
    accepted=measured.pop('acceptedFrames',[])
    body=model.getBodySet().get('firstmc')
    end=vec(model.getJointSet().get('MCP').getParentFrame().findStationLocationInAnotherFrame(state,o.Vec3(0),body))
    row=dict(id='thumb_metacarpal',label='拇指掌骨',body='firstmc',observedIndices=[1,2],
             measurementKind='thumb_base_proxy_span',estimateMethod='CMC1b_child_origin_correspondence',
             baseLengthM=float(np.linalg.norm(end)),**measured)
    row['acceptedFramesHash']=hashlib.sha256(np.asarray(accepted,dtype='<i8').tobytes()).hexdigest()
    row['measurementStatus']=measured['status']
    if measured['status'] in ('measured','review') and 'lengthM' in measured:
        scaling=segment_scale(end,measured['lengthM']);factor=scaling['scaleXYZ'][1]
        factors['firstmc']=factor;scale_xyz['firstmc']=scaling['scaleXYZ']
        row.update(status='estimated',scaleY=factor,**scaling)
    rows.append(row)
    plan = dict(schemaVersion='1.0', adapter=LEFT_ADAPTER if hand=='left' else ADAPTER_VERSION, baseModelHash=base_hash,
                sourceHash=meta['sourceHash'], hand=hand, referencePose=reference,
                bodyScaleY=factors,bodyScaleXYZ=scale_xyz,segments=rows,pathWrapRepairs=wrap_repairs,
                landmarkEstimates=dict(tips=tip_proxies,sourceAudit=SOURCE_AUDIT,thumbBase=dict(sourceIndex=1,joint='CMC1b',frame='child',status='model_estimate')),
                scalingAlgorithm='observed-spans-stable-windows-1',
                policies=dict(crossSection='preserved except distal and oblique-span uniform template estimates; never measured', fmax='preserved',
                              uncertainMeasurements='Apply a fixed observed candidate with explicit review; never infer confidence from equal output',
                              muscleLengths='OpenSim Model.scale reference-path scaling only',
                              mass='preserved', inertia='OpenSim geometric update; not validated for dynamics'))
    if side_repair:plan['sideRepair']=side_repair
    scales = o.ScaleSet()
    for body, xyz in sorted(scale_xyz.items()):
        scale = o.Scale()
        scale.setSegmentName(body)
        scale.setScaleFactors(o.Vec3(*xyz))
        scales.cloneAndAppend(scale)
    if not model.scale(state, scales, False):
        raise RuntimeError('OpenSim model scaling failed')
    state = model.initSystem()
    for c in model.getCoordinateSet():
        if not c.isDependent(state):
            c.setValue(state, reference[c.getName()], False)
    model.assemble(state)
    model.realizePosition(state)
    # Move each metacarpal subtree once, in its actual offset-frame parent.
    palm = estimate_palm(points, valid, times, np.array([joint_point(model, state, i) for i in (5,9,13,17)]))
    metacarpal_before = {}
    for digit, index in zip(range(2,6), (5,9,13,17)):
        origin = vec(model.getJointSet().get(f'CMC{digit}').getChildFrame().getPositionInGround(state))
        metacarpal_before[digit] = float(np.linalg.norm(joint_point(model, state, index)-origin))
    if palm['status'] == 'inferred':
        changes = []
        for digit, shift in zip(range(2,6), palm['shiftsGroundM']):
            joint = model.getJointSet().get(f'CMC{digit}')
            offset = o.PhysicalOffsetFrame.safeDownCast(joint.getParentFrame())
            if offset is None:
                raise ValueError('CMC parent must be an explicit offset frame')
            parent = offset.getParentFrame()
            local = vec(model.getGround().expressVectorInAnotherFrame(state, o.Vec3(*shift), parent))
            old = vec(offset.get_translation())
            changes.append((offset, old+local))
        for offset, translation in changes:
            offset.set_translation(o.Vec3(*translation))
        model.finalizeConnections()
        state = model.initSystem()
        for c in model.getCoordinateSet():
            if not c.isDependent(state):
                c.setValue(state, reference[c.getName()], False)
        model.assemble(state)
        model.realizePosition(state)
        achieved = np.array([joint_point(model,state,i) for i in (5,9,13,17)])
        palm['achievedPairsM'] = pair_lengths(achieved).tolist()
        palm['maxPairErrorM'] = float(np.max(np.abs(pair_lengths(achieved)-palm['targetPairsM'])))
        if palm['maxPairErrorM'] > .00005:
            raise RuntimeError('Palm layout verification failed')
    plan['palmLayout'] = {k:v for k,v in palm.items() if k not in ('achievedPairsM','maxPairErrorM')}
    plan['policies']['muscleLengths'] = 'Final/reference path ratio from immutable base; replace intermediate Scale result'
    for muscle in model.getMuscles():
        old = original_parameters[muscle.getName()]
        ratio = muscle.getGeometryPath().getLength(state)/original_paths[muscle.getName()]
        if not np.isfinite(ratio) or ratio <= 0:
            raise RuntimeError('Invalid final muscle path ratio')
        muscle.setOptimalFiberLength(old[1]*ratio)
        muscle.setTendonSlackLength(old[2]*ratio)
    for row in rows:
        a, b = row['observedIndices']
        row['resultLengthM'] = float(np.linalg.norm(joint_point(model, state, b) - joint_point(model, state, a)))
        if row['status'] in ('scaled','estimated') and abs(row['resultLengthM']-row['lengthM']) > 1e-6:
            raise RuntimeError('Scaled endpoint check failed: '+row['id'])
    physiology = []
    for muscle in model.getMuscles():
        old = original_parameters[muscle.getName()]
        if muscle.getMaxIsometricForce() != old[0]:
            raise RuntimeError('Fmax was unexpectedly changed')
        physiology.append(dict(id=muscle.getName(), fmax=old[0],
                               fiberLengthBefore=old[1], fiberLengthAfter=muscle.getOptimalFiberLength(),
                               tendonSlackBefore=old[2], tendonSlackAfter=muscle.getTendonSlackLength()))
    # Persisted plans omit post-scaling results, so they remain pure inputs.
    plan['segments'] = [{k: v for k, v in row.items() if k != 'resultLengthM'} for row in rows]
    all_segments = list(rows)
    for digit,index,label in [(2,5,'食指'),(3,9,'中指'),(4,13,'无名指'),(5,17,'小指')]:
        origin = vec(model.getJointSet().get(f'CMC{digit}').getChildFrame().getPositionInGround(state))
        length = float(np.linalg.norm(joint_point(model,state,index)-origin))
        if abs(length-metacarpal_before[digit]) > 1e-8:
            raise RuntimeError('Palm translation changed metacarpal length')
        all_segments.append(dict(id=f'{digit}_metacarpal',label=label+'掌骨',
                                 targetLengthM=None,baseLengthM=metacarpal_before[digit],resultLengthM=length,
                                 scaleY=1.,status='awaiting_input',reason=f'missing_cmc{digit}',
                                 layoutStatus=palm['status']))
    plan['coverageVersion']='hand-19-plus-palm-2'
    # Coverage describes missing data as well as what actually changed.
    if cached_plan is not None:
        compare = dict(cached_plan); compare.pop('coverageVersion',None)
        check = dict(plan); check.pop('coverageVersion',None)
        if compare != check:
            raise ValueError('Cached plan mismatch')
    report = dict(status='partial', dynamicsReady=False, units='m',
                  source=meta, scaledSegments=rows, muscleParameters=physiology,
                  baseUnchanged=True, modelSide=hand, baseModelName=base.name,
                  allSegments=all_segments,palmLayout=palm,
                  scaleComplete=False,
                  unobservedDimensions=['bone_width','bone_thickness','carpal_shape'],
                  unavailable=[
                      '五个指尖采用骨端代理点：末节按模板比例估计，宽厚和软组织未实测',
                      '缺少 CMC2–5 观测：四指掌骨长度保留；掌部位置按稳定 MCP 点阵推断',
                      '拇指基部按 CMC1b 对应估计，尚非独立解剖标定',
                      '缺少前臂参考：整体手位姿可拟合，腕角不作为测量结果',
                      '肌肉路径由 OpenSim 求值；未完成力臂、碰撞及动力学验证'],
                  coordinateStatus={c.getName(): 'fitted' if c.getName() in FIT_COORDS else 'dependent' if c.isDependent(state) else 'base_reference' for c in model.getCoordinateSet()})
    return model, state, plan, report, points, valid, times


def fit_clip(model, state, points, valid, times, start=30., end=42., stride=3, progress=lambda value: None):
    selection = np.flatnonzero((times >= start) & (times <= end))[::stride]
    if not len(selection):
        raise ValueError('Empty motion window')
    coords = [model.getCoordinateSet().get(name) for name in FIT_COORDS]
    observed = sorted(set(LANDMARKS)|set(TIPS))
    anchor_ids = [5, 9, 13, 17]
    reference = np.array([joint_point(model, state, i) for i in anchor_ids])
    q0 = np.array([c.getValue(state) for c in coords])
    lower = np.array([c.getRangeMin() for c in coords])
    upper = np.array([c.getRangeMax() for c in coords])
    centre = np.mean(reference, axis=0)
    initial = np.r_[np.zeros(6), np.clip(q0, lower+1e-7, upper-1e-7)]
    frames, rmses = [], []
    point_errors = {i:[] for i in observed}
    common_rmses = []
    bones = [b for b in model.getBodySet() if b.getName() not in EXCLUDED_BODIES]
    muscles = list(model.getMuscles())
    reference_lengths = [m.getGeometryPath().getLength(state) for m in muscles]
    max_path_error = 0.
    max_path_length = 0.
    first_valid = next((f for f in selection if valid[f, anchor_ids].all()), None)
    if first_valid is None:
        raise ValueError('No complete palm anchor frame')
    display_origin = points[first_valid, anchor_ids].mean(axis=0)
    for n, frame_index in enumerate(selection):
        good = np.array([i for i in observed if valid[frame_index, i]], dtype=int)
        if len(good) < 10 or not valid[frame_index, anchor_ids].all():
            frames.append(dict(time=float(times[frame_index]-start), status='missing', sourceFrame=int(frame_index)))
            continue
        if not frames or not rmses:
            r, t = rigid_alignment(reference, points[frame_index, anchor_ids])
            initial[:3] = Rotation.from_matrix(r).as_rotvec()
            initial[3:6] = t + r @ centre
        target = points[frame_index, good]
        previous = initial.copy()

        def set_state(x):
            for c, value in zip(coords, x[6:]):
                c.setValue(state, float(value), False)
            model.realizePosition(state)

        def residual(x):
            set_state(x)
            r = Rotation.from_rotvec(x[:3]).as_matrix()
            predicted = np.array([joint_point(model, state, int(i)) for i in good])
            error = ((predicted-centre) @ r.T + x[3:6] - target) / .003
            # A small temporal prior stabilises ambiguous centres without altering measurements.
            return np.r_[error.ravel(), .03*(x[6:]-previous[6:])]

        fit = least_squares(residual, initial, bounds=(np.r_[[-np.inf]*6, lower], np.r_[[np.inf]*6, upper]),
                            loss='soft_l1', f_scale=2., max_nfev=100,
                            ftol=1e-5, xtol=1e-5, gtol=1e-5)
        initial = fit.x
        set_state(initial)
        r = Rotation.from_rotvec(initial[:3]).as_matrix()
        root = np.eye(4)
        root[:3, :3] = r
        root[:3, 3] = initial[3:6] - r @ centre - display_origin
        predicted = np.array([joint_point(model, state, int(i)) for i in good])
        errors = np.linalg.norm((predicted-centre) @ r.T+initial[3:6]-target, axis=1)
        rmse = float(np.sqrt(np.mean(errors**2)))
        rmses.append(rmse)
        for index,error in zip(good,errors):
            point_errors[int(index)].append(float(error))
        common = [error for index,error in zip(good,errors) if index in LANDMARKS and index!=1]
        common_rmses.append(float(np.sqrt(np.mean(np.square(common)))))
        matrices = [(root @ matrix(b.getTransformInGround(state))).T.ravel().tolist() for b in bones]
        paths = []
        for muscle_index, muscle in enumerate(muscles):
            current = muscle.getGeometryPath().getCurrentPath(state)
            samples = []
            for i in range(current.getSize()):
                point = current.get(i)
                wrap = o.PathWrapPoint.safeDownCast(point)
                if wrap is not None:
                    surface = wrap.getWrapPath(state)
                    for j in range(surface.getSize()):
                        samples.append(vec(wrap.getParentFrame().findStationLocationInGround(state, surface.get(j))))
                else:
                    samples.append(vec(point.getLocationInGround(state)))
            p = np.array(samples)
            if len(p) < 2 or not np.isfinite(p).all():
                raise ValueError('Invalid OpenSim path: '+muscle.getName())
            length = float(np.linalg.norm(np.diff(p, axis=0), axis=1).sum())
            actual = muscle.getGeometryPath().getLength(state)
            discrepancy = abs(length-actual)
            # Fail closed on runaway wrapping, rather than rendering meter-long loops.
            if discrepancy > .001 or length > max(.15, 2*reference_lengths[muscle_index]):
                raise ValueError('Runaway or inconsistent wrapping: '+muscle.getName())
            max_path_error = max(max_path_error, discrepancy)
            max_path_length = max(max_path_length, length)
            paths.append(((p @ r.T)+root[:3, 3]).tolist())
        raw_points = [(points[frame_index, i]-display_origin).tolist() if valid[frame_index, i] else None for i in range(21)]
        frames.append(dict(time=float(times[frame_index]-start), status='fitted' if fit.success and rmse < .01 else 'review',
                           sourceFrame=int(frame_index), rmseMm=rmse*1000,
                           landmarkErrorsMm={str(int(i)):float(e*1000) for i,e in zip(good,errors)},
                           bones=matrices, paths=paths, raw=raw_points,
                           q={c.getName(): c.getValue(state) for c in model.getCoordinateSet()}))
        if n % 10 == 0:
            progress(dict(done=n+1, total=len(selection)))
    if not rmses:
        raise ValueError('No valid fitted frames')
    landmark_stats={str(i):dict(count=len(e),medianMm=float(np.median(e)*1000),p95Mm=float(np.percentile(e,95)*1000)) for i,e in point_errors.items() if e}
    distal_support={}
    for name,indices in [('ip_flexion',[2,3,4])]+[(f'{i}md_flexion',[4*i-2,4*i-1,4*i]) for i in range(2,6)]:
        count=sum(bool(valid[f['sourceFrame'],indices].all()) for f in frames if 'q' in f)
        distal_support[name]=dict(indices=indices,observedFrames=count,totalFrames=len(rmses))
    return bones, muscles, frames, dict(frameCount=len(frames), fittedFrames=len(rmses),
                                       rmseMedianMm=float(np.median(rmses)*1000),
                                       rmseP95Mm=float(np.percentile(rmses, 95)*1000),
                                       commonJointRmseMedianMm=float(np.median(common_rmses)*1000),
                                       observedIndices=observed,
                                       landmarkErrors=landmark_stats,
                                       correspondenceWarnings=[dict(index=int(i),**s) for i,s in landmark_stats.items() if s['medianMm']>10],
                                       distalObservationSupport=distal_support,
                                       coordinateRangesRad={name:[min(f['q'][name] for f in frames if 'q' in f),max(f['q'][name] for f in frames if 'q' in f)] for name in FIT_COORDS},
                                       missingFrames=sum(f['status']=='missing' for f in frames),
                                       reviewFrames=sum(f['status']=='review' for f in frames),
                                       fitCoordinates=FIT_COORDS, startS=start, endS=end,
                                       pathExportMaxErrorMm=max_path_error*1000,
                                       maxPathLengthM=max_path_length,
                                       displayOriginWorldM=display_origin.tolist())


def build(base, raw, start=30., end=42., stride=1, progress=lambda value: None):
    started = time.monotonic()
    original_hash = hashlib.sha256(base.read_bytes()).hexdigest()
    model, state, plan, report, points, valid, times = prepare(base, raw)
    state, path_qc = sample_paths(model, plan['referencePose'])
    baseline = o.Model(str(base))
    if plan['hand']=='left':repair_left_geometry(baseline)
    _, baseline_qc = sample_paths(baseline, plan['referencePose'])
    report['scalingQC'] = dict(geometryStatus='pass',palmStatus=report['palmLayout']['status'],
                               muscleParameterStatus='pass',romPaths=path_qc,baselineRomPaths=baseline_qc,
                               collisionStatus='not_supported',anatomicalStatus='awaiting_calibration')
    report['scaleRatioWarnings']=[dict(segment=r['id'],scaleY=r['scaleY']) for r in report['scaledSegments']
                                  if r.get('scaleY',1)<.65 or r.get('scaleY',1)>1.35]
    report['measurementWarnings']=[dict(segment=r['id'],reason=r.get('reason','unstable_observation'))
                                   for r in report['scaledSegments'] if r.get('measurementStatus')=='review']
    report['status']='review' if path_qc['status']=='review' or report['scaleRatioWarnings'] or report['measurementWarnings'] else 'partial'
    bones, muscles, frames, fit_report = fit_clip(model, state, points, valid, times, start, end, stride, progress)
    body_names = {body.getName() for body in bones}
    attachments = []
    for muscle in muscles:
        points_set = muscle.getGeometryPath().getPathPointSet()
        endpoints = [points_set.get(i) for i in (0, points_set.getSize()-1)]
        owners = [point.getParentFrame().findBaseFrame().getName() for point in endpoints]
        if any(owner not in body_names for owner in owners):
            raise ValueError('Visible muscle endpoint has no displayed body: '+muscle.getName())
        attachments.append(dict(muscle=muscle.getName(), originBody=owners[0], insertionBody=owners[1]))
    meshes = []
    for body_index, body in enumerate(bones):
        for i in range(body.getPropertyByName('attached_geometry').size()):
            mesh = o.Mesh.safeDownCast(body.get_attached_geometry(i))
            if mesh is None:
                continue
            vertices, faces = mesh_data(base.parent/'Geometry'/mesh.get_mesh_file())
            frame_transform = matrix(mesh.getFrame().findTransformBetween(state, body))
            vertices *= vec(mesh.get_scale_factors())
            if np.prod(vec(mesh.get_scale_factors()))<0:
                faces=np.asarray(faces).reshape(-1,3)[:,[0,2,1]].ravel().tolist()
            vertices = vertices @ frame_transform[:3, :3].T + frame_transform[:3, 3]
            meshes.append(dict(name=mesh.get_mesh_file().replace('.vtp', ''), body=body_index,
                               vertices=np.round(vertices, 7).ravel().tolist(), faces=faces))
    if hashlib.sha256(base.read_bytes()).hexdigest() != original_hash:
        raise RuntimeError('Base changed during job')
    report.update(motion=fit_report, runtimeSeconds=time.monotonic()-started,
                  opensimVersion=o.GetVersionAndDate())
    report['displayAttachments'] = dict(status='pass', missingBodies=0, endpoints=attachments,
                                        note='Owner body visibility only; not an anatomical surface-attachment validation')
    payload = dict(schemaVersion='1.0', modelName=base.stem, hand=plan['hand'],
                   bodyNames=[b.getName() for b in bones], meshes=meshes,
                   muscleNames=[m.getName() for m in muscles],
                   plan=plan, report=report, frames=frames)
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--raw', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--end', type=float, default=42)
    args = parser.parse_args()
    result = build(args.base, args.raw, end=args.end, progress=lambda p: print(json.dumps(p), flush=True))
    args.output.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(',', ':')))
    print(json.dumps(result['report']['motion'], ensure_ascii=False), flush=True)
