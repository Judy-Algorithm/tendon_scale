"""Audited route-domain correction, without changing any attachment coordinates."""
FDPI_DOMAINS = (
    ('FDP', 'FDPI-P2', 'FDPI-P3', 'radius', 'capitate'),
    ('2ndmcp_FDPI', 'FDPI-P5', 'FDPI-P6', 'secondmc', '2proxph'),
    ('2ndpm_FDPI', 'FDPI-P6_0', 'FDPI-P7', '2proxph', '2midph'),
)


def repair_wrap_domains(model):
    path = model.getMuscles().get('FDPI').updGeometryPath()
    points = path.getPathPointSet()
    names = [points.get(i).getName() for i in range(points.getSize())]
    repairs = []
    for object_name, start_name, end_name, start_body, end_body in FDPI_DOMAINS:
        a, b = names.index(start_name), names.index(end_name)
        if b != a+1:
            raise ValueError('FDPI path topology changed; revalidate wrap domains')
        owners = [points.get(i).getParentFrame().findBaseFrame().getName() for i in (a,b)]
        if owners != [start_body, end_body]:
            raise ValueError('FDPI attachment owners changed')
        wraps = path.updWrapSet()
        match = [wraps.get(i) for i in range(wraps.getSize()) if wraps.get(i).get_wrap_object() == object_name]
        if len(match) != 1:
            raise ValueError('FDPI wrapping object changed')
        wrap = match[0]
        old = [wrap.get_range(i) for i in range(2)]
        # OpenSim ranges are 1-based indexes in the original PathPointSet.
        wrap.set_range(0,a+1)
        wrap.set_range(1,b+1)
        repairs.append(dict(muscle='FDPI', wrapObject=object_name, previousRange=old,
                            range=[a+1,b+1], points=[start_name,end_name]))
    return repairs
