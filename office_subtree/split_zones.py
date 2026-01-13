from collections import defaultdict
from copy import deepcopy
from shapely import union, envelope, difference
from shapely.geometry import Polygon, Point, LineString, MultiPoint, GeometryCollection, MultiLineString
from shapely.ops import split
from descartes import PolygonPatch
import matplotlib.pyplot as plt
import os


def plot(polygons, door, boundary, filename='base_layout.png', dp=None,
         kwargs = dict(fill=None, edgecolor='blue', alpha=0.5)):
    minx, miny, maxx, maxy = boundary.bounds
    fig, ax = plt.subplots(figsize=(10, 8))
    plt.xlim((minx, maxx))
    plt.ylim((miny, maxy))

    for poly in polygons:
        patch = PolygonPatch(poly, **kwargs)
        ax.add_patch(patch)

    if door:
        plt.plot(*door.xy, marker='o', markersize=10)

    if dp:
        if not os.path.exists(dp):
            os.makedirs(dp)
    else:
        dp = os.path.dirname(os.path.abspath(__file__))
    fp = os.path.join(dp, filename)
    plt.savefig(fp)
    return ax


def __get_axis(line):
    location, length = None, None
    xs, ys = line.xy
    if _same(xs):
        location, length = 'y_axis', abs(ys[1] - ys[0])
    elif _same(ys):
        location, length = 'x_axis', abs(xs[1] - xs[0])
    return location, line.length
    

def connect_offices_to_reception(offices, reception, boundary):
    combined_reception = deepcopy(reception)
    indexes_to_connect = []

    _minx, _miny, _maxx, _maxy = boundary.bounds
    core_wall = LineString([Point(x, _miny) for x in [_minx, _maxx]])
    for i, office in enumerate(offices):
        if not reception.intersects(office): continue

        if office.intersects(core_wall):
            intersected_walls = [office.intersection(target) for target in [reception, core_wall]]
            reception_on_core_wall = reception.intersection(core_wall)
            if intersected_walls[0].length < intersected_walls[1].length and intersected_walls[1].length > reception_on_core_wall.length:
                continue

        combined_reception = union(combined_reception, office)
        indexes_to_connect.append(i)

    if indexes_to_connect:
        combined_reception = envelope(combined_reception)
    remained_offices = [office for i, office in enumerate(offices) if i not in indexes_to_connect]
    return combined_reception, remained_offices


_same = lambda alist: all(e0 == e1 for e0, e1 in zip(alist, alist[1:]))
def _get_door_location(door, reception):
    r_coords = reception.exterior.coords[:]
    lines = [LineString(line) for line in zip(r_coords[:], r_coords[1:])]

    for line in lines:
        if line.contains(door):
            xs, ys = line.xy
            if _same(xs):
                return 'y_axis'
            elif _same(ys):
                return 'x_axis'
    return None


def cut_along_reception_walls(door, reception, combined_reception, boundary):
    # door_location = _get_door_location(door, reception)

    minx, miny, maxx, maxy = combined_reception.bounds
    _minx, _miny, _maxx, _maxy = boundary.bounds
    # if door_location == 'x_axis':
    #     cuts = [LineString([Point(x, y) for x in [_minx, _maxx]])
    #                 for y in [miny, maxy]]
    # elif door_location == 'y_axis':
    # if door_location in ['x_axis', 'y_axis']:
    cuts = [LineString([Point(x, y) for y in [_miny, _maxy]])
                for x in [minx, maxx]]
    
    splitted_zones = []
    remained_zone = deepcopy(boundary)
    for i, cut in enumerate(cuts):
        if not remained_zone.contains(cut): continue
        splitted_zone, remained_zone  = split(remained_zone, cut).geoms
        if splitted_zone.area:
            splitted_zones.append(splitted_zone)
        if i == len(cuts) - 1:
            splitted_zones.append(remained_zone)
    return splitted_zones


def _get_office_location(office, zone):
    intersections = zone.boundary.intersection(office.boundary)
    
    if type(intersections) == LineString:
        location, length = __get_axis(intersections)
    elif type(intersections) == MultiLineString:
        location, length = None, None
        for wall in intersections.geoms:
            _location, _length = __get_axis(wall)
            if not length or _length > length:
                location, length = _location, _length
    elif type(intersections) == GeometryCollection:
        for target in intersections.geoms:
            if type(target) != LineString: continue
            location, length = __get_axis(target)
    return location, length


def _extend_office_within_a_zone(office, zone):
    office_location, office_length = _get_office_location(office, zone)

    extended_office = None
    minx, miny, maxx, maxy = office.bounds
    _minx, _miny, _maxx, _maxy = zone.bounds
    if office_location == 'x_axis':
        extended_office = envelope(MultiPoint([Point(_minx, _miny), Point(_maxx, maxy)]))
    elif office_location == 'y_axis':
        extended_office = envelope(MultiPoint([Point(minx, _miny), Point(maxx, _maxy)]))
    return extended_office, office_location, office_length


def eliminate_zones(splitted_zones, combined_reception, remained_offices, valid_width=4800):
    main_zones, sub_zones = [], []

    offices_to_eliminate = deepcopy(remained_offices)
    for zone in splitted_zones:
        if zone.contains(combined_reception):
            minx, *_ = zone.bounds
            diff_zone = difference(zone, combined_reception)
            if minx == 0:
                sub_zones.append(('y_axis', diff_zone))
            else:
                main_zones.append(diff_zone)
        elif not offices_to_eliminate:
            main_zones.append(zone)
        else:
            indexes_to_eliminate = []
            for i, office in enumerate(offices_to_eliminate):
                # if zone.contains(office):
                if zone.intersects(office):
                    extended_office, office_location, office_length = _extend_office_within_a_zone(office, zone)
                    _diff_zone = difference(extended_office, office)
                    remained_sub_zones = [_diff_zone] if type(_diff_zone) == Polygon else _diff_zone.geoms
                    for office_zone_remained in remained_sub_zones:
                        minx, _, maxx, _ = office_zone_remained.bounds
                        if office_location == 'x_axis' and (maxx - minx) < valid_width: continue
                        sub_zones.append((office_location, office_zone_remained))

                    diff_zone = difference(zone, extended_office)
                    main_zones.append(diff_zone)
                    indexes_to_eliminate.append(i)
            if indexes_to_eliminate:
                offices_to_eliminate = [office for i, office in enumerate(offices_to_eliminate) if i not in indexes_to_eliminate]
    return main_zones, sub_zones


def split_zones(schema, dp=None, visualization=True):
    # boundary, reception, offices, door = plot_base_layout()
    boundary, reception, door, offices = connect_office_rooms(schema)
    if visualization:
        plot([reception] + offices, door, boundary, dp=dp)

    combined_reception, remained_offices = connect_offices_to_reception(offices, reception, boundary)
    if visualization:
        plot([combined_reception] + remained_offices, door, boundary, filename='combined_reception.png', dp=dp)

    splitted_zones = cut_along_reception_walls(door, reception, combined_reception, boundary)
    main_zones, sub_zones = eliminate_zones(splitted_zones, combined_reception, remained_offices)
    if visualization:
        plot(main_zones, None, boundary, filename='main_zones.png', dp=dp)
        plot([sub_zone for _, sub_zone in sub_zones], None, boundary, filename='sub_zones.png', dp=dp)
    return boundary, main_zones, sub_zones


def _connect(rooms):
    connected_rooms = []

    def _find_index(room, connected_rooms=connected_rooms):
        for i, connected in enumerate(connected_rooms):
            if connected.intersects(room):
                return i
        return -1
    
    for room in rooms:
        index = _find_index(room)

        if not connected_rooms or index == -1:
            connected_rooms.append(room)
        else:
            connected = connected_rooms[index]
            # connected_rooms[index] = envelope(GeometryCollection([connected, room]))
            connected_rooms[index] = union(connected, room)
    return connected_rooms

def connect_office_rooms(data):
    # data = schema['roomMessage']

    boundary = Polygon([Point(coord) for coord in data['roomBoundary']])
    _reception = Polygon([Point(coord) for coord in data['non_office_area']]).envelope
    # 'non_office_area' may not be linering.
    minx, miny, maxx, maxy = _reception.bounds      
    reception = Polygon([Point(coord) for coord in [(minx, miny), (minx, maxy), (maxx, maxy), (maxx, miny)]])

    door = Point(data['publicDoor'])
    single_rooms = [Polygon([Point(coord) for coord in room]) for room in data['singleRooms']]

    connected_single_rooms = _connect(single_rooms)
    _minx, _miny, _maxx, _maxy = boundary.bounds
    for i in range(len(connected_single_rooms)):
        minx, miny, maxx, maxy = connected_single_rooms[i].bounds
        minx = max(minx, _minx)
        miny = max(miny, _miny)
        maxx = min(maxx, _maxx)
        maxy = min(maxy, _maxy)
        connected_single_rooms[i] = Polygon([Point(coord) for coord in [(minx, miny), (minx, maxy), (maxx, maxy), (maxx, miny)]])
    return boundary, reception, door, connected_single_rooms


# def adapt_inputs(region_dict):
#     adapted_region_dict = defaultdict(list)
#     for key, regions in region_dict.items():
#         for poly in regions:
#             minx, miny, maxx, maxy = poly.bounds
#             origin = (minx, miny)
#             rect = (maxx - minx, maxy - miny)
#             adapted_rect = (origin, rect)
#             adapted_region_dict[key].append(adapted_rect)
#     return adapted_region_dict
