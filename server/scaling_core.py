"""Geometry-only measurement primitives, independent of OpenSim and file formats."""
import numpy as np


def observations(points, valid, unit, interpolated=None):
    p = np.asarray(points, dtype=float).copy()
    v = np.asarray(valid, dtype=bool).copy()
    if p.ndim != 3 or p.shape[-1] != 3 or v.shape != p.shape[:2]:
        raise ValueError('Point/valid dimensions do not match')
    if unit not in ('m', 'mm'):
        raise ValueError('Explicit m or mm units required')
    p *= 0.001 if unit == 'mm' else 1
    v &= np.isfinite(p).all(axis=-1)
    if interpolated is not None:
        if np.shape(interpolated) != v.shape:
            raise ValueError('Interpolated mask dimensions do not match')
        v &= ~np.asarray(interpolated, dtype=bool)
    return p, v


def measure_span(points, valid, a, b, minimum=30, times=None):
    distances = np.linalg.norm(points[:, b] - points[:, a], axis=-1)
    keep = valid[:, a] & valid[:, b] & np.isfinite(distances)
    keep &= (distances >= .005) & (distances <= .12)
    if keep.sum() < minimum:
        return dict(status='insufficient_data', count=int(keep.sum()))
    median = np.median(distances[keep])
    mad = np.median(np.abs(distances[keep] - median))
    # Exact/noiseless inputs also need to reject isolated corrupt observations.
    keep &= np.abs(distances - median) <= max(3 * 1.4826 * mad, 1e-6)
    if keep.sum() < minimum:
        return dict(status='insufficient_data', count=int(keep.sum()))
    median = float(np.median(distances[keep]))
    mad = float(np.median(np.abs(distances[keep] - median)))
    result = dict(status='review' if mad / median > .05 else 'measured',
                lengthM=median, madM=mad, count=int(keep.sum()),
                acceptedFrames=np.flatnonzero(keep).tolist())
    result['measurementMethod'] = 'recording_robust_median'
    if result['status'] != 'review' or times is None:
        return result
    # Repeated, non-overlapping stable windows; never select by proximity to the
    # template length. A single quiet/occluded interval cannot establish length.
    t = np.asarray(times, dtype=float)
    if t.shape != distances.shape or not np.isfinite(t).all() or np.any(np.diff(t) <= 0):
        raise ValueError('Invalid measurement timestamps')
    windows = []
    raw_valid = valid[:, a] & valid[:, b] & np.isfinite(distances) & (distances >= .005) & (distances <= .12)
    for start in np.arange(t[0], t[-1]-3., 3.):
        window = (t >= start) & (t < start+3.)
        indices = np.flatnonzero(window & raw_valid)
        if len(indices) < minimum or len(indices) < .8*window.sum():
            continue
        values = distances[indices]
        center = float(np.median(values)); spread = float(np.median(np.abs(values-center)))
        halves = [values[:len(values)//2], values[len(values)//2:]]
        if spread/center > .025 or abs(np.median(halves[0])-np.median(halves[1]))/center > .03:
            continue
        windows.append(dict(startS=float(start), endS=float(start+3.), medianM=center, indices=indices))
    result['stableWindowCount'] = len(windows)
    result['reason'] = 'unstable_span_no_repeated_consensus'
    if len(windows) < 3:
        return result
    centers = np.array([w['medianM'] for w in windows])
    # Require all stable windows to agree: do not pick one of two stable modes.
    center = float(np.median(centers))
    if np.max(np.abs(centers-center)) > max(.001, .05*center):
        result['reason'] = 'conflicting_stable_windows'
        return result
    indices = np.concatenate([w['indices'] for w in windows])
    if len(indices) < .2*raw_valid.sum():
        result['reason'] = 'insufficient_stable_coverage'
        return result
    values=distances[indices]; center=float(np.median(values)); spread=float(np.median(np.abs(values-center)))
    if spread/center > .05:
        return result
    return dict(status='measured', lengthM=center, madM=spread, count=len(indices),
                acceptedFrames=indices.tolist(), measurementMethod='repeated_stable_windows',
                wholeRecordingMedianM=median, wholeRecordingMadM=mad,
                stableWindowCount=len(windows), stableCoverage=float(len(indices)/raw_valid.sum()),
                stableWindows=[{k:v for k,v in w.items() if k!='indices'} for w in windows])


def segment_scale(delta, length):
    """Keep the existing axial method where feasible; oblique spans may instead
    use a shape-preserving uniform template estimate. No relaxed axial bounds.
    """
    d=np.asarray(delta,dtype=float); base=float(np.linalg.norm(d))
    if not np.isfinite(d).all() or not np.isfinite(length) or base <= 0 or length <= 0:
        raise ValueError('Invalid segment span')
    try:
        factor=axial_factor(d,length)
        return dict(scaleXYZ=[1.,factor,1.], scaleMethod='local_y_axial', crossSection='template_preserved')
    except ValueError:
        factor=float(length/base)
        if not .5 <= factor <= 1.8:
            raise ValueError('Observed/template span ratio requires correspondence review')
        return dict(scaleXYZ=[factor]*3, scaleMethod='oblique_span_uniform_template',
                    crossSection='template_proportional_estimate')


def axial_factor(delta, length, axis=(0., -1., 0.)):
    d, a = np.asarray(delta, dtype=float), np.asarray(axis, dtype=float)
    if not np.isclose(np.linalg.norm(a), 1):
        raise ValueError('Axis must be a unit vector')
    parallel2 = float(d @ a) ** 2
    transverse2 = max(0., float(d @ d) - parallel2)
    if parallel2 < 1e-12 or length ** 2 <= transverse2:
        raise ValueError('Length cannot be attained with this axial scaling')
    scale = float(np.sqrt((length ** 2 - transverse2) / parallel2))
    if not .5 <= scale <= 1.8:
        raise ValueError('Scale outside reviewed adapter bounds')
    return scale


def rigid_alignment(source, target):
    """Return proper rotation R and t: target = source @ R.T + t. No reflection."""
    a, b = np.asarray(source), np.asarray(target)
    if len(a) < 3 or a.shape != b.shape:
        raise ValueError('At least three matching points required')
    ac, bc = a.mean(0), b.mean(0)
    u, singular, vt = np.linalg.svd((a - ac).T @ (b - bc))
    if singular[1] < 1e-10:
        raise ValueError('Degenerate alignment anchors')
    flip = np.eye(3)
    flip[-1, -1] = np.linalg.det(vt.T @ u.T)
    r = vt.T @ flip @ u.T
    return r, bc - r @ ac
