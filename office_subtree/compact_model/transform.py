


def _transform_RECT(RECT, arrangement_orientation, target_location, zone):
    (x, y), (X, Y) = zone

    if not arrangement_orientation:
        if target_location == 'down':
            _transform = lambda rx, ry, rX, rY: ((x + rx, y + ry), (rX, rY))
        else:
            _transform = lambda rx, ry, rX, rY: ((x + rx, y + Y - ry - rY), (rX, rY))
    else:
        if target_location == 'left':
            _transform = lambda rx, ry, rX, rY: ((x + ry, y + rx), (rY, rX))
        else:
            _transform = lambda rx, ry, rX, rY: ((x + X - ry - rY, y + rx), (rY, rX))
    
    return _transform(*RECT[0], *RECT[1])


def transform_RECTs(relative_RECTs, arrangement_orientation, target_location, zone):
    resulting_RECTs = [_transform_RECT(RECT, arrangement_orientation, target_location, zone) if RECT else RECT for RECT in relative_RECTs]
    return resulting_RECTs

    
def _transform_rotation(rotation, storage_orientation, wall_location):
    res = None
    if not storage_orientation:
        if rotation in [90, 270]:
            res = rotation
        else:
            if wall_location == 'down': res = rotation
            else: res = (rotation + 180) % 360
    else:
        if rotation in [90, 270]:
            res = (rotation + 90) % 360
        else:
            if wall_location == 'left': res = (rotation - 90) % 360
            else: res = (rotation + 90) % 360
    return res


def transform_components(components, arrangement_orientation, target_location, zone):
    results = [(_transform_RECT(comp[0], arrangement_orientation, target_location, zone), None if comp[1] is None else
                 _transform_rotation(comp[1], arrangement_orientation, target_location)) 
                    for comp in components if comp]
    return results