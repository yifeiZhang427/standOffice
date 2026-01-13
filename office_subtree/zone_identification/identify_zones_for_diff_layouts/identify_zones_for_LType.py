from shapely.geometry import Polygon, Point, LineString, MultiPoint, MultiLineString
from shapely import envelope, difference, unary_union
from shapely.ops import split
from shapely import affinity

from itertools import chain
from collections import defaultdict

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from zone_identification.utils_for_zone_identification import _get_walls, _adapt_a_zone, _get_walls4nonrectangle_boundary, __connect_offices_by_walls
                                                            
from zone_identification.utils_for_inputs import _get_boundary_againsts4main_zone, determine_parameters_for_component_placements
from rotate_back_new_by_yifei import rotate_back_new
from zone_identification.identify_zones import group_office_rooms_by_walls, extract_remained_zones_alongside_offices, extract_main_zone_by_max_boxes
from zone_identification.identify_zones_for_diff_layouts.utils_for_cutted_zones import assign_components_to_cutted_zones, rotate_cutted_zones_and_components, \
                                                                                        _rotate_a_zone
from zone_identification.identify_zones_when_exists_reception import _split_zone_by_cuts
from zone_identification.identify_zones_for_diff_layouts.utils_for_cutted_zones import _rotate_components_in_cutted_zones, _rotate_a_line


def __get_inner_vertexes(boundary):
    box = envelope(LineString([Point(*boundary.bounds[:2]), Point(*boundary.bounds[2:])]))
    inner_vertexes = [vertex for vertex in boundary.exterior.coords if box.contains(Point(*vertex))]

    return inner_vertexes


def _cut_LType_via_inner_vertex(boundary, direction='Y'):
    inner_vertex = __get_inner_vertexes(boundary)[0]

    _x, _y = inner_vertex

    minx, miny, maxx, maxy = boundary.bounds
    cut = LineString([Point(x, _y) for x in [minx, maxx]]) if direction == 'Y' else \
            LineString([Point(_x, y) for y in [miny, maxy]])
    
    cutted_zones = list(split(boundary, cut).geoms)
    cutted_zones = [envelope(MultiPoint(cutted_zone.exterior.coords)) for cutted_zone in cutted_zones]

    # cutted_zones = sorted(cutted_zones, key=lambda zone: -zone.area)
    cutted_zones = sorted(cutted_zones, key=lambda zone: zone.bounds[0])
    return cutted_zones
    # return [envelope(MultiPoint(zone.exterior.coords)) for zone in cutted_zones]


def _cut_LIType_via_inner_vertexes(boundary, direction='X'):
    inner_vertexes = __get_inner_vertexes(boundary)

    minx, miny, maxx, maxy = boundary.bounds

    if direction == 'X':
        inner_vertexes = sorted(inner_vertexes, key=lambda vertex: (vertex[0], vertex[1]))
        cuts = [LineString([Point(_x, y) for y in [miny, maxy]]) for _x, _ in inner_vertexes]
        cutted_zones = list(split(boundary, MultiLineString(cuts)).geoms)

        cutted_zones = sorted(cutted_zones, key=lambda zone: zone.bounds[0])
        if cutted_zones[-1].area > cutted_zones[0].area:
            cutted_zones = cutted_zones[::-1]
    else:
        cutted_zones = _cut_LType_via_inner_vertex(inner_vertexes[0], boundary)

    return cutted_zones


def _check_inner_edges_in_cutted_zone(zone, inner_edges):
    _walls = _get_walls(*zone.bounds)

    _inner_edge_inside = [edge for edge in inner_edges if zone.intersection(edge).length > 0][0]

    axis_of_inner_edge_inside = [axis for axis, wall in _walls.items() if wall.intersection(_inner_edge_inside).length > 0][0]
    return axis_of_inner_edge_inside


def _rotate_door(door, cutted_zones, rotations4cutted_zones, boundary_centriod):
    door_in_cutted_zones = [i for i, zone in enumerate(cutted_zones) if zone.intersects(door)]
    if door_in_cutted_zones:
        i = door_in_cutted_zones[0]
        rotated_door = affinity.rotate(door, rotations4cutted_zones[i], origin=boundary_centriod)
    else:
        rotated_door = door
    return rotated_door


def _determine_rotations4cutted_zones(cutted_zones, boundary):
    box = envelope(LineString([Point(*boundary.bounds[:2]), Point(*boundary.bounds[2:])]))

    _edges = _get_walls4nonrectangle_boundary(boundary)
    _is_a_point = lambda line: all(coord0[0] == coord1[0] and coord0[1] == coord1[1] for coord0, coord1 in zip(line.coords, line.coords[1:]))
    inner_edges = [edge for edge in _edges if box.contains(edge) and not _is_a_point(edge)]
    passageway_axises4cutted_zones = [_check_inner_edges_in_cutted_zone(zone, inner_edges) for zone in cutted_zones]

    _rotation_map = {'-y': 0, '-x': 90, '+x': -90, '+y': 180}
    rotations4cutted_zones = [_rotation_map[axis] for axis in passageway_axises4cutted_zones]
    return rotations4cutted_zones


def determine_parameters_for_cutted_zone(cutted_zone, boundary_lines=[]):
    boundaries = [_get_boundary_againsts4main_zone(axises, cutted_zone, cutted_zone, [], None,
                                                   boundary_lines=boundary_lines) for axises in [['-y', '+y'], ['-x', '+x']]]

    main_zone = _adapt_a_zone(cutted_zone)
    desk_orientation = 0
    passageway_location = 'down'
    return main_zone, desk_orientation, passageway_location, boundaries



def identify_zones4LType_like(data, cut_layout_func=_cut_LType_via_inner_vertex):
    boundary = Polygon([Point(coord) for coord in data['roomBoundary']])

    cutted_zones = cut_layout_func(boundary, direction='X')
    
    rotations4cutted_zones = _determine_rotations4cutted_zones(cutted_zones, boundary)

    boundary_centriod = boundary.centroid
    rotated_cutted_zones = [_rotate_a_zone(zone, rotation, center=boundary_centriod) for zone, rotation in zip(cutted_zones, rotations4cutted_zones)]


    boundary_lines = _get_walls4nonrectangle_boundary(boundary)
    boundary_lines_in_cutted_zones = [[line for line in boundary_lines if cutted_zone.intersection(line).length > 0]
                                    for cutted_zone in cutted_zones]
    rotated_boundary_lines_groups = _rotate_components_in_cutted_zones(boundary_lines_in_cutted_zones, _rotate_a_line, rotations4cutted_zones=rotations4cutted_zones, centriod=boundary_centriod)

    parameters4cutted_zones = [determine_parameters_for_cutted_zone(rotated_zone, rotated_boundary_lines) 
                                                                    for rotated_zone, rotated_boundary_lines in zip(rotated_cutted_zones, rotated_boundary_lines_groups)]

    door = Point(*data['publicDoor'])
    rotated_door = _rotate_door(door, cutted_zones, rotations4cutted_zones, boundary_centriod)
    return (boundary, door), (rotations4cutted_zones, boundary_centriod), \
            rotated_cutted_zones, rotated_door, parameters4cutted_zones



# def _group_office_rooms_by_doors(offices, doors):
#     doors4offices = [[door for door in doors if office.intersects(door)] for office in offices]

#     offices_by_axises = defaultdict(list)
#     for office, doors in zip(offices, doors4offices):
#         if not doors: continue
        
#         door_axises = [axis for axis, line in _get_walls(*office.bounds).items() if line.intersects(doors[0])]
#         if door_axises:
#             door_axis = door_axises[0]
#             sign = '-' if door_axis[0] == '+' else '+'
#             wall_axis = sign + door_axis[1]
#             offices_by_axises[wall_axis].append(office)

#     return offices_by_axises

def _group_office_rooms_by_doors(offices, office_doors, boundary_lines):
    _is_boundary_line = lambda line, boundary_lines: any(line.intersection(boundary_line).length > 0 for boundary_line in boundary_lines)

    offices_by_axises = defaultdict(list)
    for office, office_door in zip(offices, office_doors):
        
        door_axises = [axis for axis, line in _get_walls(*office.bounds).items() if line.intersects(office_door)]
        for door_axis in door_axises:
            sign = '-' if door_axis[0] == '+' else '+'
            wall_axis = sign + door_axis[1]
            if _is_boundary_line(_get_walls(*office.bounds)[wall_axis], boundary_lines):
                offices_by_axises[wall_axis].append(office)

    return offices_by_axises

def __exclude_zone_without_wall(axis, sub_zone, rect_boundary, boundary_lines):
    line_in_axis4sub_zone = _get_walls(*sub_zone.bounds)[axis]

    line_in_axis4rect_boundary = _get_walls(*rect_boundary.bounds)[axis]
    boundary_line_in_axis = [line for line in boundary_lines if line.intersection(line_in_axis4rect_boundary).length > 0][0]

    diff = difference(boundary_line_in_axis, line_in_axis4sub_zone)
    if diff.length > 0:
        intersected_boundary_line = boundary_line_in_axis.intersection(line_in_axis4sub_zone)

        _minx, _miny, _maxx, _maxy = intersected_boundary_line.bounds
        minx, miny, maxx, maxy = sub_zone.bounds

        point4box = Point(_minx, maxy) if axis == '-y' else \
                    Point(_minx, miny) if axis == '+y' else \
                    Point(maxx, _miny) if axis == '-x' else \
                    Point(minx, _miny)
        sub_zone_with_boundary_line = envelope(MultiPoint(list(intersected_boundary_line.coords) + [point4box]))
        sub_zone_without_boundary_line = difference(sub_zone, sub_zone_with_boundary_line)
    else:
        sub_zone_with_boundary_line, sub_zone_without_boundary_line = sub_zone, None
    return sub_zone_with_boundary_line, sub_zone_without_boundary_line


def _exclude_sub_zones_without_walls(sub_zones, rect_boundary, boundary_lines):
    sub_zones_with_boundary_lines = defaultdict(list)
    sub_zones_without_boundary_lines = defaultdict(list)

    for axis, zones in sub_zones.items():
        if axis != '-y': 
            sub_zones_with_boundary_lines[axis] = zones
            continue

        for zone in zones:
            sub_zone_with_boundary_line, sub_zone_without_boundary_line = __exclude_zone_without_wall(axis, zone, rect_boundary, boundary_lines)
            sub_zones_with_boundary_lines[axis].append(sub_zone_with_boundary_line)
            if not sub_zone_without_boundary_line.is_empty:
                sub_zones_without_boundary_lines[axis].append(sub_zone_without_boundary_line)
    return sub_zones_with_boundary_lines, sub_zones_without_boundary_lines


def _aggregate(sub_zones_list):
    aggregated_sub_zones = defaultdict(list)

    for sub_zones in sub_zones_list:
        for axis, zones in sub_zones.items():
            aggregated_sub_zones[axis] += zones
    return aggregated_sub_zones


# def __add_missing_sub_zones_in_connected_box(offices_by_axises, max_boxes_by_at_axises, sub_zones):
#     missing_sub_zones = defaultdict(list)
    
#     for axis, box in max_boxes_by_at_axises.items():
#         if axis not in offices_by_axises.keys(): continue

#         for office in offices_by_axises[axis] + sub_zones[axis]:
#             remained_box = difference(box, office)

#         if not remained_box.is_empty:
#             missing_sub_zones[axis].append(envelope(remained_box))
#     return missing_sub_zones



def _extract_remained_zones_in_each_rotated_cutted_zone(rotated_cutted_zone, 
                                                        rotated_reception=None, rotated_offices=[], rotated_office_doors=[],
                                                        rotated_boundary_lines=[]):
    boundary = rotated_cutted_zone

    # connected_offices_by_walls = group_office_rooms_by_walls(rotated_offices, boundary)
    offices_by_axises = _group_office_rooms_by_doors(rotated_offices, rotated_office_doors, rotated_boundary_lines)
    connected_offices_by_walls, sub_zones_inside = __connect_offices_by_walls(offices_by_axises)
    max_boxes_by_at_axises, sub_zones = extract_remained_zones_alongside_offices(connected_offices_by_walls, boundary)
    # sub_zones = _aggregate([sub_zones_inside, sub_zones_outside])


    # missing_sub_zones = _add_back_mising_sub_zones(offices_by_axises, max_boxes_by_at_axises, sub_zones)

    # sub_zones = {key: [zone for zone in zones if not zone.is_empty and not zone.intersection(door).length > 0] for key, zones in sub_zones.items()}
    # _sub_zones = _cut_sub_zones_by_door(sub_zones, Point(*data['publicDoor']), boundary)

    sub_zones = {key: [zone for zone in zones if not zone.is_empty] for key, zones in sub_zones.items()}
    sub_zones, sub_zones_without_boundary_lines = _exclude_sub_zones_without_walls(sub_zones, rotated_cutted_zone, rotated_boundary_lines)

    main_zone = extract_main_zone_by_max_boxes(max_boxes_by_at_axises, boundary)

    if rotated_reception:
        if rotated_reception.intersection(main_zone).area > 0:
            main_zone = difference(main_zone, rotated_reception)
            main_zones = _cut_LIType_via_inner_vertexes(main_zone, direction='X')

        new_sub_zones = defaultdict(list)
        for key, zones in sub_zones.items():
            for zone in zones:
                if zone.intersection(rotated_reception).area > 0:
                    minx, _, maxx, _ = rotated_reception.bounds
                    _, _miny, _, _maxy = zone.bounds
                    cuts = [LineString([Point(x, _miny), Point(x, _maxy)]) for x in [minx, maxx]]
                    reduced_zones = split(zone, MultiLineString(cuts))
                    new_sub_zones[key] += list(reduced_zones.geoms)
                else:
                    new_sub_zones[key] += [zone]
        sub_zones = new_sub_zones
    else:
        main_zones = [main_zone]

    return sub_zones_without_boundary_lines, sub_zones, main_zones


def _init(data, cut_layout_func=_cut_LType_via_inner_vertex):
    _Point = lambda x, y: Point(int(x), int(y))

    boundary = Polygon([_Point(*coord) for coord in data['roomBoundary']])
    offices = [Polygon([_Point(*coord) for coord in room]) for room in data['singleRooms']]
    reception = Polygon([_Point(*coord) for coord in data['non_office_area']])
    # office_doors = [_Point(door['center']['x'], door['center']['y']) for door in data['doorWindowDatas']]
    office_doors = [LineString([_Point(*coord) for coord in coords]) for coords in data['singleRoomsDoor']]
    main_door = _Point(*data['publicDoor'])

    boundary_lines = _get_walls4nonrectangle_boundary(boundary)


    cutted_zones = cut_layout_func(boundary, direction='X')
    # offices_in_cutted_zones = [[envelope(cutted_zone.intersection(office)) for office in offices if cutted_zone.intersection(office).area > 0] for cutted_zone in cutted_zones]
    reception_in_cutted_zones, offices_in_cutted_zones, office_doors_in_cutted_zones, main_door_in_cutted_zones, \
         boundary_lines_in_cutted_zones = assign_components_to_cutted_zones(cutted_zones, 
                                                                            reception=reception, offices=offices, office_doors=office_doors, main_door=main_door,
                                                                            boundary_lines=boundary_lines)
    
    rotations4cutted_zones = _determine_rotations4cutted_zones(cutted_zones, boundary)
    boundary_centriod = boundary.centroid
    rotated_cutted_zones, \
    rotated_receptions, rotated_offices_groups, rotated_office_doors_groups, rotated_main_doors, \
    rotated_boundary_lines_groups = rotate_cutted_zones_and_components(cutted_zones, rotations4cutted_zones, boundary_centriod,
                                                                       reception_in_cutted_zones=reception_in_cutted_zones, offices_in_cutted_zones=offices_in_cutted_zones, office_doors_in_cutted_zones=office_doors_in_cutted_zones, main_door_in_cutted_zones=main_door_in_cutted_zones,
                                                                       boundary_lines_in_cutted_zones=boundary_lines_in_cutted_zones)

    return (boundary, reception, offices, office_doors, main_door),\
            (cutted_zones, reception_in_cutted_zones, offices_in_cutted_zones, office_doors_in_cutted_zones, main_door_in_cutted_zones,
            boundary_lines_in_cutted_zones), (rotations4cutted_zones, boundary_centriod), \
            (rotated_cutted_zones, rotated_receptions, rotated_offices_groups, rotated_office_doors_groups, rotated_main_doors,
            rotated_boundary_lines_groups)


def identify_zones4LType_like_when_exists_office_rooms(data, cut_layout_func=_cut_LType_via_inner_vertex):
    (boundary, reception, offices, office_doors, main_door), \
        (cutted_zones, reception_in_cutted_zones, offices_in_cutted_zones, office_doors_in_cutted_zones, main_door_in_cutted_zones,
        boundary_lines_in_cutted_zones), (rotations4cutted_zones, boundary_centriod), \
        (rotated_cutted_zones, rotated_receptions, rotated_offices_groups, rotated_office_doors_groups, rotated_main_doors,
        rotated_boundary_lines_groups) = _init(data, cut_layout_func)

    # remained_zones_in_rotated_cutted_zones = [_extract_remained_zones_in_each_rotated_cutted_zone(rotated_cutted_zone, 
    #                                                                                               rotated_reception=rotated_reception, rotated_offices=rotated_offices, rotated_office_doors=rotated_office_doors,
    #                                                                                               rotated_boundary_lines=rotated_boundary_lines) 
    #                                           for rotated_cutted_zone, rotated_reception, rotated_offices, rotated_office_doors, rotated_boundary_lines in zip(
    #                                               rotated_cutted_zones, rotated_receptions, rotated_offices_groups, rotated_office_doors_groups, rotated_boundary_lines_groups)]
    
    remained_zones_in_rotated_cutted_zones = []
    targeted_zones = list(list(tpl) for tpl in zip(rotated_cutted_zones, rotated_receptions, rotated_offices_groups, rotated_office_doors_groups, rotated_boundary_lines_groups))
    for i, (_, rotation) in enumerate(zip(targeted_zones, rotations4cutted_zones)):
        rotated_cutted_zone, rotated_reception, rotated_offices, rotated_office_doors, rotated_boundary_lines = targeted_zones[i]
        sub_zones_without_boundary_lines, sub_zones, main_zones = _extract_remained_zones_in_each_rotated_cutted_zone(rotated_cutted_zone, 
                                                                                                                        rotated_reception=rotated_reception, rotated_offices=rotated_offices, rotated_office_doors=rotated_office_doors,
                                                                                                                        rotated_boundary_lines=rotated_boundary_lines) 
        remained_zones_in_rotated_cutted_zones.append((sub_zones, main_zones))
        if sub_zones_without_boundary_lines:
            polygons = list(chain.from_iterable(sub_zones_without_boundary_lines.values()))
            polygons_rotated_back = [_rotate_a_zone(poly, -rotation, boundary_centriod) for poly in polygons]
            if i >= len(targeted_zones) - 1: continue
            rotated_polygons4next_rotated_zone = [(_rotate_a_zone(poly, rotations4cutted_zones[i+1], boundary_centriod)) for poly in polygons_rotated_back]
            next_rotated_zone = targeted_zones[i+1][0]
            rotated_polygons_intersected_with_next_rotated_zone = [rotated_poly for rotated_poly in rotated_polygons4next_rotated_zone if rotated_poly.intersects(next_rotated_zone)]
            if rotated_polygons_intersected_with_next_rotated_zone:
                targeted_zones[i+1][0] = unary_union([next_rotated_zone] + rotated_polygons_intersected_with_next_rotated_zone)

    main_zones2cutted_zones = {_adapt_a_zone(main_zone): i
                               for i, (_, main_zones) in enumerate(remained_zones_in_rotated_cutted_zones)
                                for main_zone in main_zones}                 
    sub_zones2cutted_zones = {_adapt_a_zone(sub_zone): i 
                                for i, (sub_zones, main_zones) in enumerate(remained_zones_in_rotated_cutted_zones) 
                                    for axis, sub_zones in sub_zones.items() 
                                        for sub_zone in sub_zones}
    inputs4cutted_zones = [determine_parameters_for_component_placements(None, offices, cutted_zone, 
                                                                         None, sub_zones, main_zones,
                                                                         boundary_lines=boundary_lines_in_cutted_zone) 
                           for cutted_zone, offices, boundary_lines_in_cutted_zone, (sub_zones, main_zones) in zip(
                               rotated_cutted_zones, rotated_offices_groups, rotated_boundary_lines_groups, remained_zones_in_rotated_cutted_zones)
                               if main_zones]
    
    rotated_main_door = [rotated_main_door for rotated_main_door in rotated_main_doors][0]
    offices = [_adapt_a_zone(office) for office in chain.from_iterable(offices_in_cutted_zones)]
    return (boundary, main_door), (rotations4cutted_zones, boundary_centriod), \
            rotated_cutted_zones, rotated_main_door, rotated_receptions, \
            rotated_office_doors_groups, offices_in_cutted_zones, sub_zones2cutted_zones, main_zones2cutted_zones, \
            inputs4cutted_zones