import os
from shapely.geometry import Point, LineString, GeometryCollection, Polygon, MultiPolygon
from shapely import envelope, difference
from shapely.ops import split
from itertools import chain
from copy import deepcopy
from collections import defaultdict

from split_zones import plot


def init(data, dp=None, visualization=False):
    boundary = Polygon([Point(coord) for coord in data['roomBoundary']])
    _reception = Polygon([Point(coord) for coord in data['non_office_area']]).envelope
    # 'non_office_area' may not be linering.
    minx, miny, maxx, maxy = _reception.bounds      
    reception = Polygon([Point(coord) for coord in [(minx, miny), (minx, maxy), (maxx, maxy), (maxx, miny)]])

    door = Point(data['publicDoor'])
    offices = [Polygon([Point(coord) for coord in room]) for room in data['singleRooms']]
    
    return boundary, reception, door, offices

_get_walls = lambda _minx, _miny, _maxx, _maxy: {
    '-x': LineString([Point(_minx, y) for y in [_miny, _maxy]]),
    '+x': LineString([Point(_maxx, y) for y in [_miny, _maxy]]),
    '-y': LineString([Point(x, _miny) for x in [_minx, _maxx]]),
    '+y': LineString([Point(x, _maxy) for x in [_minx, _maxx]])
}

def connect_offices_to_reception(offices, reception, boundary):
    reception_walls = _get_walls(*reception.bounds)
    boundary_walls = _get_walls(*boundary.bounds)

    indexes_to_connect = []
    for i, office in enumerate(offices):
        if any(wall.intersects(office) for axis, wall in reception_walls.items()):
            if any(wall.intersects(office) for _, wall in boundary_walls.items()): 
                continue
            indexes_to_connect.append(i)

    offices_to_connect = [office for i, office in enumerate(offices) if i in indexes_to_connect]
    remained_offices = [office for i, office in enumerate(offices) if i not in indexes_to_connect]    
    unioned_reception = envelope(GeometryCollection(offices_to_connect + [reception]))
    return unioned_reception, remained_offices


def _get_connected_walls(office, reception, boundary):
    connected_walls = []

    if all(not office.intersects(zone) for zone in [reception, boundary]):
        return connected_walls
    
    _get_walls = lambda _type, _minx, _miny, _maxx, _maxy: [
        (_type, '-x', LineString([Point(_minx, y) for y in [_miny, _maxy]])),
        (_type, '+x', LineString([Point(_maxx, y) for y in [_miny, _maxy]])),
        (_type, '-y', LineString([Point(x, _miny) for x in [_minx, _maxx]])),
        (_type, '+y', LineString([Point(x, _maxy) for x in [_minx, _maxx]]))
    ]
    walls = _get_walls('boundary', *boundary.bounds)
    if reception:
        walls += _get_walls('reception', *reception.bounds)

    for wall in walls:
        _type, axis, line = wall
        if office.intersects(line):
            intersection = office.intersection(line)
            if _type == 'reception' and type(intersection) == Point:
                continue
            connected_walls.append(((_type, axis), intersection.length))
    return connected_walls


def _find_index_to_connect(office, connected_offices):
    for i, o in enumerate(connected_offices):
        if office.intersects(o):
            return i
    return -1

def _find_wall_types_to_connect(offcie, offices_in_groups):
    _wall_types = []
    for _wall_type, _offices in offices_in_groups.items():
        index = _find_index_to_connect(offcie, _offices)
        if index != -1: 
            _wall_types.append((_wall_type, index))
    return _wall_types

def _find_longest_intersection(intersections):
    max_length, max_wall_type = None, None
    for _wall_type, length in intersections:
        if max_length is None or length > max_length:
            max_length, max_wall_type = length, _wall_type
    return max_wall_type, max_length
    
def _get_the_closest(office, axis, offices):
    _minx, _miny, *_ = office.bounds

    _index, _distance = -1, None
    for i, o in enumerate(offices):
        minx, miny, *_ = o.bounds
        distance = abs(minx - _minx) if axis.endswith('y') else abs(miny - _miny)
        if not _distance or distance < _distance:
            _index, _distance = i, distance
    return _index

def group_offices(offices, reception, boundary):
    offices_in_groups = defaultdict(list)
    _remained_offices = []
    for i, office in enumerate(offices):
        connected_walls = _get_connected_walls(office, None, boundary)
        if len(connected_walls) == 1:
            offices_in_groups[connected_walls[0][0]].append(office)
        elif len(connected_walls) > 1:
            _remained_offices.append(office)


    for office in _remained_offices:
        # _wall_types = _find_wall_types_to_connect(office, offices_in_groups)
        _WALL_TYPES = _get_connected_walls(office, None, boundary)

        _WALL_TYPES_to_connect = [_wall_type for _wall_type, _ in _WALL_TYPES if _wall_type in offices_in_groups.keys()]
        fullsize_in = False
        for _wall_type in _WALL_TYPES_to_connect:
            _, axis = _wall_type

            _index = _get_the_closest(office, axis, offices_in_groups[_wall_type])

            _minx, _miny, _maxx, _maxy = offices_in_groups[_wall_type][_index].bounds
            _xs, _ys = [_minx, _maxx], [_miny, _maxy]

            minx, miny, maxx, maxy = office.bounds
            xs, ys = [minx, maxx], [miny, maxy]
            if axis.endswith('y'):
                ys = _ys
            elif axis.endswith('x'):
                xs = _xs
            _cutted_office = envelope(LineString([Point(x, y) for x, y in zip(xs, ys)]))
            offices_in_groups[_wall_type].append(_cutted_office)
            if _cutted_office.area == office.area:
                fullsize_in = True

        if len(_WALL_TYPES_to_connect) == len(_WALL_TYPES): continue

        _remained_WALLs = set([_wall for _wall, _ in _WALL_TYPES]) - set(_WALL_TYPES_to_connect)
        if len(_WALL_TYPES_to_connect) == 0:
            _remained_WALL_TYPES = [(_wall, length) for _wall, length in _WALL_TYPES if _wall in _remained_WALLs]
            _longest_wall_type, _ = _find_longest_intersection(_remained_WALL_TYPES)
            offices_in_groups[_longest_wall_type].append(office)
        elif not fullsize_in:
            _wall_type = _remained_WALLs.pop()
            offices_in_groups[_wall_type].append(office)

        # _WALL_TYPES = _get_connected_walls(office, None, boundary)
        # for _wall_type, length in _WALL_TYPES:
        #     if _wall_type not in offices_in_groups.keys():
        #         # _cutted_office = office
        #         continue
            
        #     _, axis = _wall_type
        #     _index = _get_the_closest(office, axis, offices_in_groups[_wall_type])
        #     _minx, _miny, _maxx, _maxy = offices_in_groups[_wall_type][_index].bounds
        #     _xs, _ys = [_minx, _maxx], [_miny, _maxy]

        #     minx, miny, maxx, maxy = office.bounds
        #     xs, ys = [minx, maxx], [miny, maxy]
        #     if axis.endswith('y'):
        #         ys = _ys
        #     elif axis.endswith('x'):
        #         xs = _xs
        #     _cutted_office = envelope(LineString([Point(x, y) for x, y in zip(xs, ys)]))
        #     offices_in_groups[_wall_type].append(_cutted_office)
    return offices_in_groups


def connect_offices_in_groups(offices_in_groups):
    connected_offices_in_groups = defaultdict(list)

    for key, offices in offices_in_groups.items():
        connected_offices = []
        for office in offices:
            if not connected_offices:
                connected_offices.append(office)
                continue
            index = _find_index_to_connect(office, connected_offices)
            if index == -1:
                connected_offices.append(office)
            else:
                connected_offices[index] = envelope(GeometryCollection([connected_offices[index], office]))
        connected_offices_in_groups[key] = connected_offices
    return connected_offices_in_groups


def _get_BOX(connected_office_list, _wall_type, boundary):
    boundary_walls = _get_walls(*boundary.bounds)

    _, axis = _wall_type
    wall = boundary_walls[axis]

    __get_minmax_bound = lambda i, office_list, minmax=min: minmax(office.bounds[i] for office in office_list)
    if axis.endswith('y'):
        sign = axis.split('y')[0]
        y = __get_minmax_bound(-1, connected_office_list, minmax=max) if sign == '-' else \
                __get_minmax_bound(1, connected_office_list, minmax=min)
        minx, *_ = wall.bounds
        BOX = envelope(GeometryCollection([wall, Point(minx, y)]))
        RECTs = [envelope(GeometryCollection([office, Point(office.bounds[0], y)])) for office in connected_office_list]
    else:
        sign = axis.split('x')[0]
        x = __get_minmax_bound(-2, connected_office_list, minmax=max) if sign == '-' else \
            __get_minmax_bound(0, connected_office_list, minmax=min)
        _, miny, *_ = wall.bounds
        BOX = envelope(GeometryCollection([wall, Point(x, miny)]))
        RECTs = [envelope(GeometryCollection([office, Point(x, office.bounds[1])])) for office in connected_office_list]
    # remained_BOX = difference(BOX, envelope(GeometryCollection(RECTs)))
    remained_BOX = deepcopy(BOX)
    for RECT in RECTs:
        remained_BOX = difference(remained_BOX, RECT)
    return BOX, remained_BOX



def extract_remained_sub_zones(connected_offices_in_groups, boundary, unioned_reception):
    BOXs = []
    sub_zones = []
    for _wall_type, connected_office_list in connected_offices_in_groups.items():
        # RECT = envelope(GeometryCollection(connected_office_list))
        # _type, _axis = _wall_type
        # BOX = envelope(GeometryCollection([RECT, boundary_walls[_axis]]))
        # remained = difference(BOX, RECT)
        if not connected_office_list: continue
        BOX, remained = _get_BOX(connected_office_list, _wall_type, boundary)
        BOXs.append((_wall_type, BOX))
        if not remained: continue

        if type(remained) == Polygon and not remained.intersects(unioned_reception):
            sub_zones.append((_wall_type, remained))
        elif type(remained) == MultiPolygon:
            for sub_zone in remained.geoms:
                if not sub_zone.intersects(unioned_reception):
                    sub_zones.append((_wall_type, sub_zone))
    return sub_zones, BOXs


def cut_according_to_reception(reception, main_BOX, boundary):
    # minx, _, maxx, _ = reception.bounds
    # _minx, _miny, _maxx, _maxy = main_BOX.bounds
    # _reception = envelope(LineString([Point(minx, _miny), Point(*reception.bounds[2:])]))
    # extended_reception = envelope(GeometryCollection([_reception, Point(minx, _maxy)]))
    # _main_zone = difference(extended_reception, _reception)
    # splitted_BOXs = difference(main_BOX, extended_reception)
    # if type(splitted_BOXs) == MultiPolygon:
    #     main_zones = [splitted_BOXs.geoms[0]] + [_main_zone] + [splitted_BOXs.geoms[1]]
    # elif type(splitted_BOXs) == Polygon:
    #     if minx == _minx:
    #         main_zones = [_main_zone] + [splitted_BOXs]
    #     elif maxx == _maxx:
    #         main_zones = [splitted_BOXs] + [_main_zone]

    minx, _, maxx, _ = reception.bounds
    _minx, _miny, _maxx, _maxy = boundary.bounds
    CUTS = [LineString([Point(x, _y) for _y in [_miny, _maxy]])
                for x in [minx, maxx]]
    
    if minx == _minx:
        splitted_BOXs = split(main_BOX, CUTS[-1])
    elif maxx == _maxx:
        splitted_BOXs = split(main_BOX, CUTS[0])
    else:
        # splitted_BOXs = split(main_BOX, CUTS)
        splitted_BOXs = []
        _main_BOX = envelope(LineString([Point(*main_BOX.bounds[:2]), Point(*main_BOX.bounds[-2:])]))
        _remained_BOX = deepcopy(_main_BOX)
        for i, cut in enumerate(CUTS):
            _BOX, _remained_BOX = list(split(_remained_BOX, cut).geoms)
            splitted_BOXs.append(_BOX)
            if i == len(CUTS) - 1:
                splitted_BOXs.append(_remained_BOX)
    _splitted_BOXs = splitted_BOXs.geoms if type(splitted_BOXs) in [MultiPolygon, GeometryCollection] else splitted_BOXs
    main_zones = [difference(BOX, reception) if BOX.intersects(reception) else BOX for BOX in _splitted_BOXs]
    # return main_zones
    return [zone for zone in main_zones if zone]


def _eliminate_overlapped_zones(sub_zones):
    def __find_overlapped_zone(zone, zones):
        for i, (_, z) in enumerate(zones):
            if zone.intersection(z).area > 0:
                return i
        return -1
    
    if len(sub_zones) <= 1: return sub_zones

    resulting_zones = sub_zones[:1]
    for _wall_type, zone in sub_zones[1:]:
        index = __find_overlapped_zone(zone, resulting_zones)

        if index == -1:
            resulting_zones.append((_wall_type, zone))
        else:
            r_wall_type, target_zone = resulting_zones[index]
            intersection = target_zone.intersection(zone)
            if intersection.area / zone.area >= intersection.area / target_zone.area:
                _zone = difference(zone, intersection)
                resulting_zones.append((_wall_type, _zone))
            else:
                resulting_zones[index] = (r_wall_type, difference(target_zone, intersection))
    return resulting_zones

def _eliminate(_BOXs, main_zone):
    _main_zone = deepcopy(main_zone)
    for _, BOX in _BOXs:
        if _main_zone.intersection(BOX).area == 0: 
            continue
        _main_zone = difference(_main_zone, BOX)
    return _main_zone
    
def split_zones(data, dp=None, visualization=False):
    boundary, reception, door, offices = init(data, dp=dp, visualization=True)
    unioned_reception, remained_offices = connect_offices_to_reception(offices, reception, boundary)
    if visualization:
        plot([reception] + offices, door, boundary, dp=dp, filename='base_layout.png')
        plot([unioned_reception] + remained_offices, door, boundary, dp=dp, filename='offices_connected_to_reception.png')

    offices_in_groups = group_offices(remained_offices, unioned_reception, boundary)
    # _offices = [o for olist in offices_in_groups.values() for o in olist]
    # _offices = [envelope(GeometryCollection(olist)) for olist in offices_in_groups.values()]
    connected_offices_in_groups = connect_offices_in_groups(offices_in_groups)
    _offices = [o for olist in connected_offices_in_groups.values() for o in olist]
    if visualization:
        plot([unioned_reception] + _offices, door, boundary, dp=dp, filename='offices_in_groups.png')

    # sub_zones, BOXs = extract_remained_sub_zones(connected_offices_in_groups, boundary, unioned_reception)
    # if visualization:
    #     _sub_zones = list([zone for _, zone in sub_zones])
    #     plot(_sub_zones, door, boundary, dp=dp, filename='sub_zones.png')

    # main_BOX = deepcopy(boundary)
    # for _, BOX in BOXs:
    #     main_BOX = difference(main_BOX, BOX)
    # if visualization:
    #     plot([main_BOX], door, boundary, dp=dp, filename='main_BOX.png')

    # main_zones = cut_according_to_reception(unioned_reception, main_BOX, boundary)
    # if visualization:
    #     plot(main_zones, door, boundary, dp=dp, filename='main_zones.png')
    # _main_zones = [(('boundary', '-y'), zone) for zone in main_zones]
    # return boundary, _main_zones, sub_zones


    sub_zones, main_zones = [], []
    main_zone = deepcopy(boundary)
    top_boundary = ('boundary', '+y')
    if top_boundary in connected_offices_in_groups.keys():
        _connected_offices_in_groups = {top_boundary: connected_offices_in_groups[top_boundary]}
        _sub_zones, _BOXs = extract_remained_sub_zones(_connected_offices_in_groups, main_zone, unioned_reception)
        if _sub_zones: sub_zones += _sub_zones
        main_zone = _eliminate(_BOXs, main_zone)
        del connected_offices_in_groups[top_boundary]

    splitted_boundaries = cut_according_to_reception(unioned_reception, main_zone, boundary)
    if visualization:
        plot(splitted_boundaries, door, boundary, dp=dp, filename='splitted_boundaries.png')
    for main_zone in splitted_boundaries:
        _boundary = main_zone
        _connected_offices_in_groups = {key: [o for o in _offices if _boundary.intersection(o).area > 0] for key, _offices in connected_offices_in_groups.items()}
        _sub_zones, _BOXs = extract_remained_sub_zones(_connected_offices_in_groups, _boundary, unioned_reception)
        if _sub_zones: sub_zones += _sub_zones
        _main_zone = _eliminate(_BOXs, main_zone)
        if _main_zone: main_zones.append(_main_zone)


    sub_zones = _eliminate_overlapped_zones(sub_zones)

    if visualization:
        _sub_zones = [zone for _, zone in sub_zones]
        plot(_sub_zones, door, boundary, dp=dp, filename='sub_zones.png')
        plot(main_zones, door, boundary, dp=dp, filename='main_zones.png')
    _main_zones = [(('boundary', '-y'), zone) for zone in main_zones]
    return boundary, _main_zones, sub_zones, unioned_reception, connected_offices_in_groups


def split_zones_new(data, dp=None, visualization=False):
    boundary, reception, door, _offices = init(data, dp=dp, visualization=True)
    _minx, _miny, _maxx, _maxy = boundary.bounds
    offices = [envelope(LineString([
        Point(max(minx, _minx), max(miny, _miny)),
        Point(min(maxx, _maxx), min(maxy, _maxy))
        ])) for minx, miny, maxx, maxy in [office.bounds for office in _offices]]
    unioned_reception, remained_offices = connect_offices_to_reception(offices, reception, boundary)

    sub_zones, main_zones = [], []
    global_connected_offices_in_groups = defaultdict(list)
    splitted_boundaries = cut_according_to_reception(unioned_reception, boundary, boundary)
    for _splitted_boundary in splitted_boundaries:
        _offices_in_groups = group_offices(remained_offices, unioned_reception, _splitted_boundary)
        _connected_offices_in_groups = connect_offices_in_groups(_offices_in_groups)
        _sub_zones, _BOXs = extract_remained_sub_zones(_connected_offices_in_groups, _splitted_boundary, unioned_reception)
        if _sub_zones: sub_zones += _sub_zones
        _main_zone = _eliminate(_BOXs, _splitted_boundary)
        if _main_zone: main_zones.append(_main_zone)

        for key, connected_offices in _connected_offices_in_groups.items():
            global_connected_offices_in_groups[key] += connected_offices

    sub_zones = _eliminate_overlapped_zones(sub_zones)

    if visualization:
        _sub_zones = [zone for _, zone in sub_zones]
        plot(_sub_zones, door, boundary, dp=dp, filename='sub_zones.png')
        plot(main_zones, door, boundary, dp=dp, filename='main_zones.png')
    _main_zones = [(('boundary', '-y'), zone) for zone in main_zones]
    return boundary, _offices, _main_zones, sub_zones, unioned_reception, global_connected_offices_in_groups



def _intersects_with_offices(wall, its_axis, connected_offices_in_groups):
    facing_axis = '+x' if its_axis == '-x' else '-x'

    for _, zones in connected_offices_in_groups.items():
        for zone in zones:
            walls = _get_walls(*zone.bounds)
            facing_wall = walls[facing_axis]
            if wall.intersection(facing_wall).length > 0:
                return True
    return False

def identify_neighbors_in_X_axis_for_main_zones(main_zones, unioned_reception, boundary, connected_offices_in_groups):
    walls = {
        'reception': _get_walls(*unioned_reception.bounds),
        'boundary': _get_walls(*boundary.bounds)
    }

    _neighbors = ['wall', 'wall']
    neighbors4main_zones = []
    for _, zone in main_zones:
        neighbors = deepcopy(_neighbors)
        
        _walls = _get_walls(*zone.bounds)
        if _walls['-y'].intersection(walls['reception']['+y']).length > 0:
            neighbors = ['islands'] * 2

            if _intersects_with_offices(_walls['-x'], '-x', connected_offices_in_groups):
                neighbors[0] = 'office_wall'
            elif _walls['-x'].intersection(walls['boundary']['-x']).length > 0:
                neighbors[0] = _neighbors[0]

            if _intersects_with_offices(_walls['+x'], '+x', connected_offices_in_groups):
                neighbors[1] = 'office_wall' 
            elif _walls['+x'].intersection(walls['boundary']['+x']).length > 0:
                neighbors[1] = 'wall' 
        elif _walls['+x'].intersection(walls['reception']['-x']).length > 0:
            neighbors[1] = 'main_passageway'
            if not _walls['-x'].intersects(walls['boundary']['-x']):
                neighbors[0] = 'office_wall'
        elif _walls['-x'].intersection(walls['reception']['+x']).length > 0:
            neighbors[0] = 'main_passageway'
            if not _walls['+x'].intersects(walls['boundary']['+x']):
                neighbors[1] = 'office_wall'
        neighbors4main_zones.append(neighbors)
    print(neighbors4main_zones)
    return neighbors4main_zones


def _intersects_with_any_office(wall, offices):
    # for _, zones in connected_offices_in_groups.items():
    for zone in offices:
        _walls = _get_walls(*zone.bounds)
        if any(_wall.intersection(wall).length for _wall in _walls.values()) > 0:
            return True
    return False

def identify_neighbors_in_Y_axis_for_main_zones(main_zones, offices):
    _neighbors = ['wall', 'wall']
    neighbors4main_zones = []
    for _, zone in main_zones:
        neighbors = deepcopy(_neighbors)

        _walls = _get_walls(*zone.bounds)
        if _intersects_with_any_office(_walls['-y'], offices):
            neighbors[0] = 'office_wall'
        
        if _intersects_with_any_office(_walls['+y'], offices):
            neighbors[1] = 'office_wall'
        neighbors4main_zones.append(neighbors)
 
    return neighbors4main_zones
