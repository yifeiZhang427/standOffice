from shapely.geometry import Polygon, Point, GeometryCollection, LineString, MultiPolygon, MultiLineString
from shapely import envelope, difference, contains, covers
from shapely.ops import split
from collections import defaultdict
from itertools import chain
from copy import deepcopy

from .identify_zones_when_exists_reception import determine_parameters_for_component_placements
from .utils_for_zone_identification import _get_walls, __getXY, \
        __connect_offices_by_walls, extract_remained_zones_alongside_offices, extract_main_zone_by_max_boxes

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from split_zones_ver2 import plot
from general.latest_spacing import main_passageway_width




def __intersects_with_boundary_walls(office_walls, boundary_walls):
    resulting_boundary_walls = []
    for axis, line in boundary_walls.items():
        if any(line.intersection(o_line).length > 0 for _, o_line in office_walls.items()):
            resulting_boundary_walls.append((axis, line))
    return resulting_boundary_walls


def _determine_axis_for_zone_at_corner(zone, other_connected_zones_by_walls, boundary_walls):
    intersected_boundary_walls = __intersects_with_boundary_walls(_get_walls(*zone.bounds), boundary_walls)
    walls_to_connect = [(__getXY(zone)[1], __getXY(other_connected_zones_by_walls[axis])[1] if axis in other_connected_zones_by_walls.keys() else 0) if axis.endswith('y') else
                        (__getXY(zone)[0], __getXY(other_connected_zones_by_walls[axis])[0] if axis in other_connected_zones_by_walls.keys() else 0) for axis, _ in intersected_boundary_walls]
    gaps = [abs(length - _length) for length, _length in walls_to_connect]
    index_of_min_gap = [i for i, (length, _length) in enumerate(walls_to_connect) if abs(length - _length) == min(gaps)][0]
    axis, _ = intersected_boundary_walls[index_of_min_gap]
    return axis

def group_office_rooms_by_walls(offices, boundary):
    _offices_assigned2walls = defaultdict(list)
    _offices_at_corners = []

    boundary_walls = _get_walls(*boundary.bounds)
    for office in offices:
        intersected_boundary_walls = __intersects_with_boundary_walls(_get_walls(*office.bounds), boundary_walls)

        if len(intersected_boundary_walls) == 1:
            axis, _ = intersected_boundary_walls[0]
            _offices_assigned2walls[axis].append(office)
        elif len(intersected_boundary_walls) > 1:
            _offices_at_corners.append(office)
            # for later identification
    
    connected_offices_by_walls, _ = __connect_offices_by_walls(_offices_assigned2walls)

    for office in _offices_at_corners:
        axis = _determine_axis_for_zone_at_corner(office, connected_offices_by_walls, boundary_walls)
        _offices_assigned2walls[axis].append(office)
            
    connected_offices_by_walls, _ = __connect_offices_by_walls(_offices_assigned2walls)
    return connected_offices_by_walls


def _cut_sub_zones_by_door(sub_zones, door_center, boundary, door_width=main_passageway_width):
    boundary_walls = _get_walls(*boundary.bounds)
    walls_with_door = [axis for axis, line in boundary_walls.items() if contains(line, door_center)]
    if not walls_with_door or not set(walls_with_door).intersection(set(sub_zones.keys())) :
        return sub_zones
    
    def __get_cuts(axis, zone):
        minx, miny, maxx, maxy = zone.bounds
        d_x, d_y = door_center.x, door_center.y
        if axis.endswith('y'):
            cuts = MultiLineString([LineString([Point(x, miny), Point(x, maxy)]) for x in [d_x - door_width / 2, d_x + door_width / 2]])
        else:
            cuts = MultiLineString([LineString([Point(minx, y), Point(maxx, y)]) for y in [d_y - door_width / 2, d_y + door_width / 2]])
        return cuts

    _resulting_sub_zones = deepcopy(sub_zones)
    for axis in walls_with_door:
        indexes = [i for i, zone in enumerate(sub_zones[axis]) if covers(zone, door_center)]

        remained_zones_dict = defaultdict(list)
        for i in indexes:
            zone = sub_zones[axis][i]
            cuts = __get_cuts(axis, zone)
                
            for splitted_zone in split(zone, cuts).geoms:
                _rough_door = envelope(cuts)

                if splitted_zone.intersection(_rough_door).area > 0: continue
                remained_zones_dict[i].append(splitted_zone)
        
        for i in indexes:
            del _resulting_sub_zones[axis][i]
        _resulting_sub_zones[axis] += list(chain.from_iterable(remained_zones_dict.values()))
    return _resulting_sub_zones

def identify_zones(data, dp=None, visualization=False, door_width=1200):
    boundary = Polygon([Point(coord) for coord in data['roomBoundary']])
    x, y = data['publicDoor']
    door = LineString([Point(x - door_width/2, y), Point(x + door_width/x, y)])

    if data['singleRooms']:
        offices = [Polygon([Point(coord) for coord in room]) for room in data['singleRooms']]

        connected_offices_by_walls = group_office_rooms_by_walls(offices, boundary)
        max_boxes_by_at_axises, sub_zones = extract_remained_zones_alongside_offices(connected_offices_by_walls, boundary)
        # sub_zones = {key: [zone for zone in zones if not zone.is_empty and not zone.intersection(door).length > 0] for key, zones in sub_zones.items()}
        _sub_zones = _cut_sub_zones_by_door(sub_zones, Point(*data['publicDoor']), boundary)
        sub_zones = {key: [zone for zone in zones if not zone.is_empty] for key, zones in _sub_zones.items()}

        main_zone = extract_main_zone_by_max_boxes(max_boxes_by_at_axises, boundary)

        if visualization:
            plot(connected_offices_by_walls.values(), door, boundary, dp=dp, filename='connected_offices.png')
            plot(chain.from_iterable(sub_zones.values()), door, boundary, dp=dp, filename='sub_zones.png')
            plot([main_zone], door, boundary, dp=dp, filename='main_zone.png')
    else:
        offices = []
        sub_zones = {}
        main_zone = boundary

    return offices, boundary, door, sub_zones, main_zone


# def determine_parameters_for_component_placements(boundary, door, _sub_zones, _main_zone):
#     def _adapt_a_zone(zone):
#         minx, miny, maxx, maxy = zone.bounds
#         origin = (minx, miny)
#         rect = (maxx - minx, maxy - miny)
#         return (origin, rect)
    
#     def _get_storage_orientation4sub_zone(axis):
#         return 1 if axis.endswith('x') else 0
    
#     def _get_wall_location4sub_zone(axis):
#         if axis.endswith('x'):
#             wall_location = ('left' if axis.split('x')[0] == '-' else 'right')
#         else:
#             wall_location = ('down' if axis.split('y')[0] == '-' else 'up')
#         return wall_location


#     def _get_boundary_againsts4main_zone(axises, main_zone, boundary, boundary_against=('wall', 'wall')):
#         main_zone_walls = _get_walls(*main_zone.bounds)
#         boundary_walls = _get_walls(*boundary.bounds)
#         # for i, axis in enumerate(axises):
#         #     if all(main_zone_walls[axis].intersection(boundary_wall).length == 0 for _, boundary_wall in boundary_walls.items()):
#         #         boundary_against[i] = 'office_wall'
#         boundary_against = tuple(['office_wall' if all(main_zone_walls[axis].intersection(boundary_wall).length == 0 for _, boundary_wall in boundary_walls.items())  else 'wall' 
#                                   for axis in axises])
#         return boundary_against


#     boundary_against_in_Y_axis4main_zones = [_get_boundary_againsts4main_zone(['-y', '+y'], _main_zone, boundary)]
#     boundary_against4main_zones = [_get_boundary_againsts4main_zone(['-x', '+x'], _main_zone, boundary)]

#     main_zones = [_adapt_a_zone(_main_zone)]
#     desk_orientations4main_zones = [0] * len(main_zones)
#     passageway_locations4main_zones = ['down'] * len(main_zones)

#     sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones = [], [], []
#     for axis, zones in _sub_zones.items():
#         for sub_zone in zones:
#             adapted_zone = _adapt_a_zone(sub_zone)
#             storage_orientations4sub_zone = _get_storage_orientation4sub_zone(axis)
#             wall_locations4sub_zone = _get_wall_location4sub_zone(axis)
#             sub_zones.append(adapted_zone)
#             storage_orientations4sub_zones.append(storage_orientations4sub_zone)
#             wall_locations4sub_zones.append(wall_locations4sub_zone)

#     return main_zones, desk_orientations4main_zones, passageway_locations4main_zones, \
#             boundary_against_in_Y_axis4main_zones, boundary_against4main_zones, \
#             sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, boundary


def prepare_inputs_without_reception(schema, dp=None, visualization=False):
    offices, boundary, door, sub_zones, main_zone = identify_zones(schema, dp=dp, visualization=visualization)
    
    # inputs = determine_parameters_for_component_placements(boundary, door, sub_zones, main_zone)
    inputs = determine_parameters_for_component_placements(None, offices, boundary, door, sub_zones, [main_zone])
    return Point(*schema['publicDoor']), inputs


# def prepare_inputs_for_layout_with_nothing(schema, boundary_against_in_Y_axis4main_zones, boundary_against4main_zones,
#                    dp=None, visualization=False):
#     schema['singleRooms'] = []
#     boundary, door, sub_zones, main_zone = identify_zones(schema, dp=dp, visualization=visualization)

#     inputs = determine_parameters_for_component_placements(boundary, door, sub_zones, main_zone)

#     boundary_against_in_Y_axis4main_zones, boundary_against4main_zones = boundary_against_in_Y_axis4main_zones, boundary_against4main_zones
#     inputs = list(inputs)
#     inputs[3] = [boundary_against_in_Y_axis4main_zones]
#     inputs[4] = [boundary_against4main_zones]
#     return inputs