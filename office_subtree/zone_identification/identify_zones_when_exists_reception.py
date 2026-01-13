from collections import defaultdict
from itertools import chain
from copy import deepcopy
from shapely.geometry import Polygon, LineString, Point, GeometryCollection, MultiPolygon
from shapely import envelope, difference, contains
from shapely.ops import split

from .utils_for_zone_identification import _get_walls, __intersects_with_boundary_walls, _determine_axis_for_zone_at_corner,\
                                            __connect_offices_by_walls, extract_remained_zones_alongside_offices, extract_main_zone_by_max_boxes
from .utils_for_inputs import determine_parameters_for_component_placements
from compact_model.bound_main_zone import __with_door_alongside_wall

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from split_zones_ver2 import plot
from general.configs import sizes
from general.latest_spacing import main_passageway_width


def group_office_rooms_by_walls(offices, boundary=None, reception=None):
    if not reception and not boundary:
        return None
    
    exclusive_walls = {}
    if boundary:
        boundary_walls = _get_walls(*boundary.bounds)
        exclusive_walls = {('boundary', axis): line for axis, line in boundary_walls.items()}

    if reception:
        reception_walls = _get_walls(*reception.bounds)
        for axis, line in reception_walls.items():
            # if any(line.intersection(_line).length > 0 for _axis, _line in boundary_walls.items()): continue
            exclusive_walls[('reception', axis)] = line


    _offices_assigned2walls = defaultdict(list)
    _offices_at_corners = []
    _isolated_offices = []

    for office in offices:
        intersected_boundary_walls = __intersects_with_boundary_walls(office, exclusive_walls)

        if len(intersected_boundary_walls) == 1:
            axis, _ = intersected_boundary_walls[0]
            _offices_assigned2walls[axis].append(office)
        elif len(intersected_boundary_walls) > 1:
            _offices_at_corners.append(office)
            # for later identification
        else:
            _isolated_offices.append(office)
            # office connected to offices but not reception or boundary
    
    connected_offices_by_walls, _ = __connect_offices_by_walls(_offices_assigned2walls)

    for office in _offices_at_corners:
        axis = _determine_axis_for_zone_at_corner(office, connected_offices_by_walls, exclusive_walls)
        _offices_assigned2walls[axis].append(office)
            
    connected_offices_by_walls, _ = __connect_offices_by_walls(_offices_assigned2walls)
    return _isolated_offices, connected_offices_by_walls


def _find_office_group_to_connect(isolated_office, connected_offices_by_walls):
    for wall, office_group in connected_offices_by_walls.items():
        if isolated_office.intersects(office_group):
            return (wall, office_group)
    return None


def _filter_remained_zones_by_boundary(remained_zones, door, reception):
    resulting_zones = {('boundary', key): [zone for zone in zones 
                                    if not zone.is_empty and 
                                        not zone.intersects(door) and
                                         not zone.intersects(reception)] 
                        for key, zones in remained_zones.items()}
    return resulting_zones


def _split_zone_by_cuts(zone, cuts):
    cutted_zones = []

    remained_zone = envelope(zone)
    for i, cut in enumerate(cuts):
        results = list(split(remained_zone, cut).geoms)
        if len(results) == 1:
            remained_zone = results[0]
        else:
            cutted_zone, remained_zone = split(remained_zone, cut).geoms
            cutted_zones.append(cutted_zone)
        if i == len(cuts) - 1:
            cutted_zones.append(remained_zone)
    return cutted_zones


def _remove_reception_by_cuts(sub_zones, reception, door, boundary):
    def __get_cuts_from_reception_for_axis(reception, axis, boundary=boundary):
        vertexes = _find_vertexes_within_main_zone(reception, boundary)
        minx, miny, maxx, maxy = boundary.bounds
        if axis.endswith('y'):
            cuts = [LineString([Point(x, miny-70), Point(x, maxy+70)]) for x, _ in sorted(vertexes, key=lambda coords: coords[0])]
        else:
            cuts = [LineString([Point(minx-70, y), Point(maxx+70, y)]) for _, y in sorted(vertexes, key=lambda coords: coords[1])]
        return cuts
    
    resulting_zones_dict = defaultdict(list)
    for key, zones in sub_zones.items():
        cuts = __get_cuts_from_reception_for_axis(reception, key[1])

        resulting_zones = []
        for zone in zones:
            if zone.is_empty: continue

            # if not zone.intersects(reception):
            #     resulting_zones.append(zone)
            # else:
            if zone.intersects(reception):
                _cutted_zones = _split_zone_by_cuts(zone, cuts)
                resulting_zones += [zone for zone in _cutted_zones if not zone.intersects(door) and
                                        not zone.intersection(reception).area > 0]
            else:
                resulting_zones += [zone]
        resulting_zones_dict[('boundary', key)] += resulting_zones
    return resulting_zones_dict


def _combine_sub_zones_with_main_zones(sub_zones, main_zones):
    def __find_exactly_matched_sub_zones(main_zone, sub_zones):
        minx, miny, maxx, maxy = main_zone.bounds

        indexes = []
        for key, zones in sub_zones.items():
            for i, zone in enumerate(zones):
                if zone.intersects(main_zone):
                    intersection = zone.intersection(main_zone)
                    _, axis = key
                    if axis.endswith('y') and intersection.length == (maxx - minx):
                        indexes.append((key, i))
                    elif axis.endswith('x') and intersection.length == (maxy - miny):
                        indexes.append((key, i))
        return indexes
    
    combined_main_zones = []
    indexes_list = []
    for main_zone in main_zones:
        indexes = __find_exactly_matched_sub_zones(main_zone, sub_zones)
        combined_main_zone = envelope(GeometryCollection([main_zone] + [sub_zones[key][i] for key, i in indexes]))
        combined_main_zones.append(combined_main_zone)

        indexes_list += indexes

    indexes = set(indexes_list)
    remained_sub_zones = {key: [zone for i, zone in enumerate(zones) 
                                if i not in [_i for _key, _i in indexes if _key == key]] 
                            for key, zones in sub_zones.items()}
    return combined_main_zones, remained_sub_zones



def _find_vertexes_within_main_zone(reception_box, _main_zone_excluding_office_boxes):
    vertexes = []
    for coords in reception_box.exterior.coords:
        vertex = Point(coords)
        if _main_zone_excluding_office_boxes.contains(vertex):
            vertexes.append(coords)
    return vertexes


def __expand_reception_box(reception, doors4reception={}, main_passageway_width=main_passageway_width):
    minx, miny, maxx, maxy = reception.bounds
    for (_, axis), with_door in doors4reception.items():
        if not with_door: continue
        if axis.endswith('x'):
            if axis.startswith('-'):
                minx -= main_passageway_width
            else:
                maxx += main_passageway_width
        else:
            if axis.startswith('-'):
                miny -= main_passageway_width
            else:
                maxy += main_passageway_width

    expanded_reception = envelope(LineString([Point(minx, miny), Point(maxx, maxy)]))
    return expanded_reception


def _cut_main_zone_by_reception(reception, boundary):
    # vertexes = _find_vertexes_within_main_zone(reception, boundary)
    minx, miny, maxx, maxy = reception.bounds
    vertexes = [(x, maxy) for x in [minx, maxx]]

    _, miny, _, maxy = boundary.bounds
    cuts = [LineString([Point(x, miny-70), Point(x, maxy+70)]) for x, _ in sorted(vertexes, key=lambda coords: coords[0])]

    cutted_main_zones = _split_zone_by_cuts(boundary, cuts)
    main_zones = [difference(cutted_main_zone, reception) for cutted_main_zone in cutted_main_zones]
    return [zone for zone in main_zones if not zone.is_empty]

# def _map(zone):
#     minx, miny, maxx, maxy = zone.bounds
#     return envelope(LineString([Point(minx - 70, miny - 70), Point(maxx + 35, maxy + 35)])) 


def identify_zones(data, dp=None, visualization=False, door_width=1200):
    boundary = Polygon([Point(coord) for coord in data['roomBoundary']])
    x, y = data['publicDoor']
    door = LineString([Point(x - door_width/2, y), Point(x + door_width/x, y)])

    reception = Polygon([Point(coord) for coord in data['non_office_area']]).envelope

    main_door = data['publicDoor']
    reception_walls = _get_walls(*reception.bounds)
    doors4reception = {('reception', axis): __with_door_alongside_wall(axis, wall_line, main_door) for axis, wall_line in reception_walls.items()}


    if data['singleRooms']:
        # 'non_office_area' may not be linering.
        
        # reception = _map(_reception)
        # boundary = _map(boundary)
        # make it compatible with offices' coordinates

        offices = [Polygon([Point(coord) for coord in room]) for room in data['singleRooms']]
        # _minx, _miny, _maxx, _maxy = boundary.bounds
        # _offices = [envelope(LineString([
        #     Point(max(minx, _minx), max(miny, _miny)),
        #     Point(min(maxx, _maxx), min(maxy, _maxy))
        #     ])) for minx, miny, maxx, maxy in [office.bounds for office in offices]]


        _isolated_offices, connected_offices_by_walls = group_office_rooms_by_walls(offices, boundary, reception)
        for isolated_office in _isolated_offices:
            wall, office_group = _find_office_group_to_connect(isolated_office, connected_offices_by_walls)
            connected_offices_by_walls[wall] = envelope(GeometryCollection([office_group, isolated_office]))

        offices_connected_to_boundary = {axis: office for (category, axis), office in connected_offices_by_walls.items() if category == 'boundary'}
        max_boxes_by_at_axises, sub_zones_alongside_boundary = extract_remained_zones_alongside_offices(offices_connected_to_boundary, boundary)

        offices_connected_to_reception = [office for (category, _), office in connected_offices_by_walls.items() if category == 'reception']
        reception_box = envelope(GeometryCollection([reception] + offices_connected_to_reception))
        # _sub_zones_alongside_boundary = _filter_remained_zones_by_boundary(sub_zones_alongside_boundary, door, reception_box)

        _sub_zones_alongside_reception = difference(reception_box, reception)
        for office in offices_connected_to_reception:
            _sub_zones_alongside_reception = difference(_sub_zones_alongside_reception, office)
        if _sub_zones_alongside_reception.is_empty:
            _sub_zones_alongside_reception = []
        elif type(_sub_zones_alongside_reception) == MultiPolygon:
            _sub_zones_alongside_reception = list(_sub_zones_alongside_reception.geoms)
        elif type(_sub_zones_alongside_reception) == Polygon:
            _sub_zones_alongside_reception = [_sub_zones_alongside_reception]

        _isolated_offices, _sub_zones_by_reception_walls = group_office_rooms_by_walls(_sub_zones_alongside_reception, reception=reception_box)
        doors4reception = {key: True if key in _sub_zones_by_reception_walls.keys() else value for key, value in doors4reception.items()}

        _sub_zones_by_reception_walls = {key: [value] for key, value in _sub_zones_by_reception_walls.items()
                                                        if not value.intersects(door)}
        # sub_zones = {**_sub_zones_alongside_boundary, **_sub_zones_by_reception_walls}
        _main_zone_excluding_office_boxes = extract_main_zone_by_max_boxes(max_boxes_by_at_axises, boundary)
        # main_zone = difference(_main_zone, reception_box)

        if visualization:
            plot(connected_offices_by_walls.values(), door, boundary, dp=dp, filename='connected_offices.png')

        if _main_zone_excluding_office_boxes.intersects(reception_box):
            # vertexes = _find_vertexes_within_main_zone(reception_box, boundary)
            # _, miny, _, maxy = boundary.bounds
            # cuts = [LineString([Point(x, miny-70), Point(x, maxy+70)]) for x, _ in sorted(vertexes, key=lambda coords: coords[0])]

            # cutted_main_zones = _split_zone_by_cuts(_main_zone_excluding_office_boxes, cuts)
            # _main_zones = [difference(cutted_main_zone, reception_box) for cutted_main_zone in cutted_main_zones]
            _main_zones = _cut_main_zone_by_reception(reception_box, _main_zone_excluding_office_boxes)
        else:
            _main_zones = [_main_zone_excluding_office_boxes]
        
        _reception_box = __expand_reception_box(reception_box, doors4reception=doors4reception, main_passageway_width=main_passageway_width)
        _sub_zones_alongside_boundary = _remove_reception_by_cuts(sub_zones_alongside_boundary, _reception_box, door, boundary)
        main_zones, remained_sub_zones = _combine_sub_zones_with_main_zones(_sub_zones_alongside_boundary, _main_zones)
        sub_zones = {**remained_sub_zones, **_sub_zones_by_reception_walls}

        _minx, _miny, _maxx, _maxy = boundary.bounds
        _take_area_inside_boundary = lambda minx, miny, maxx, maxy: envelope(LineString([
            Point(max(minx, _minx), max(miny, _miny)),
            Point(min(maxx, _maxx), min(maxy, _maxy))]))
        main_zones = [_take_area_inside_boundary(*zone.bounds) for zone in main_zones]
        sub_zones = {key: [_take_area_inside_boundary(*zone.bounds) for zone in zones] for key, zones in sub_zones.items() if zones}

        if visualization:
            plot(connected_offices_by_walls.values(), door, boundary, dp=dp, filename='connected_offices.png')
    else:
        offices = []
        sub_zones = {}
        main_zones = _cut_main_zone_by_reception(reception, boundary)

    def __filter_zones_by_min_width(zones, width=sizes['printer_set'][1]):
        resulting_zones = []
        for zone in zones:
            minx, miny, maxx, maxy = zone.bounds
            # note that it does not work for L-type tiles
            if maxx - minx <= width or maxy - miny <= width:
                continue
            resulting_zones.append(zone)
        return resulting_zones
    
    main_zones = __filter_zones_by_min_width(main_zones)
    sub_zones = {wall: __filter_zones_by_min_width(sub_zones) for wall, sub_zones in sub_zones.items()}

    if visualization:
        plot(list(chain.from_iterable(sub_zones.values())), door, boundary, dp=dp, filename='sub_zones.png')
        plot(main_zones, door, boundary, dp=dp, filename='main_zone.png')

    return reception, offices, boundary, door, sub_zones, main_zones


def prepare_inputs_with_reception(schema, dp=None, visualization=False):
    reception, offices, boundary, door, sub_zones, main_zones = identify_zones(schema, dp=dp, visualization=visualization)
    
    inputs = determine_parameters_for_component_placements(reception, offices, boundary, door, sub_zones, main_zones)
    return Point(*schema['publicDoor']), inputs