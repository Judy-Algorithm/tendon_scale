"""Static MCP-layout inference. No inferred CMC position is treated as a measurement."""
import hashlib
import numpy as np
from scaling_core import rigid_alignment

PAIRS = [(i, j) for i in range(4) for j in range(i+1, 4)]


def pair_lengths(points):
    return np.stack([np.linalg.norm(points[..., j, :]-points[..., i, :], axis=-1) for i,j in PAIRS], axis=-1)


def estimate_palm(points, valid, times, reference, window=None):
    """Choose a stable 3-second shape window; rigid motion alone is not instability."""
    ids = [5, 9, 13, 17]
    p = np.asarray(points)[:, ids]
    complete = np.asarray(valid)[:, ids].all(1) & np.isfinite(p).all((1, 2))
    ref = np.asarray(reference)
    rsv = np.linalg.svd(ref-ref.mean(0), compute_uv=False)
    if rsv[1]/max(rsv[0], 1e-12) < .05:
        return dict(status='review', reason='degenerate_model_palm')
    windows = [window] if window is not None else [(float(t), float(t+3)) for t in np.arange(times[0], times[-1]-3, 1)]
    candidates = []
    for start, end in windows:
        mask = complete & (times >= start) & (times <= end)
        indices = np.flatnonzero(mask)
        if len(indices) < 30:
            continue
        frames = p[indices]
        distances = pair_lengths(frames)
        med = np.median(distances, axis=0)
        mad = np.median(np.abs(distances-med), axis=0)
        keep = (np.abs(distances-med) <= np.maximum(3*1.4826*mad, .002)).all(1)
        sv = np.linalg.svd(frames-frames.mean(1, keepdims=True), compute_uv=False)
        keep &= sv[:, 1]/np.maximum(sv[:, 0], 1e-12) >= .05
        indices = indices[keep]
        if len(indices) < 30 or keep.mean() < .5:
            continue
        residual = np.percentile(np.abs(pair_lengths(p[indices])-med), 95)
        if residual > .002:
            continue
        candidates.append((float(residual), start, end, indices))
    if not candidates:
        return dict(status='review', reason='no_stable_palm_window')
    score, start, end, indices = min(candidates, key=lambda c: (c[0], c[1]))
    aligned = []
    for frame in p[indices]:
        r, t = rigid_alignment(frame, ref)
        aligned.append(frame@r.T+t)
    target = np.median(aligned, axis=0)
    target += ref.mean(0)-target.mean(0)
    shifts = target-ref
    if np.max(np.linalg.norm(shifts, axis=1)) > .015:
        return dict(status='review', reason='palm_shift_exceeds_15mm', windowS=[start, end])
    return dict(status='inferred', evidence='inferred_layout', windowS=[start, end],
                frames=int(len(indices)), stablePairP95M=score,
                acceptedFramesHash=hashlib.sha256(np.asarray(indices, dtype='<i8').tobytes()).hexdigest(),
                targetM=target.tolist(), shiftsGroundM=shifts.tolist(),
                basePairsM=pair_lengths(ref).tolist(), targetPairsM=pair_lengths(target).tolist())
