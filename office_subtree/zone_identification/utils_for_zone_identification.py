from copy import deepcopy
from collections import defaultdict
from itertools import chain

from shapely.geometry import LineString, Point, GeometryCollection, MultiPolygon, Polygon, MultiLineString
from shapely import envelope, difference
from shapely.ops import split


def _get_walls4nonrectangle_boundary(boundary):
    _vertexes = boundary.exterior.coords
    _edges = [(v0, v1) for v0, v1 in zip(_vertexes,_vertexes[1:])]
    _edges = [((p0, min(p1, p3)), (p2, max(p1, p3))) if p0 == p2 else
              ((min(p0, p2), p1), (max(p0, p2), p3)) for (p0, p1), (p2, p3) in _edges]
    edges = [LineString(edge) for edge in _edges]
    # edges = [LineString([Point(*v0), Point(*v1)]) for v0, v1 in zip(_vertexes, _vertexes[1:])]
    return edges


_get_walls = lambda _minx, _miny, _maxx, _maxy: {
    '-x': LineString([Point(_minx, y) for y in [_miny, _maxy]]),
    '+x': LineString([Point(_maxx, y) for y in [_miny, _maxy]]),
    '-y': LineString([Point(x, _miny) for x in [_minx, _maxx]]),
    '+y': LineString([Point(x, _maxy) for x in [_minx, _maxx]])
}


def __getXY(office):
    minx, miny, maxx, maxy = office.bounds
    X, Y = (maxx - minx), (maxy - miny)
    return (X, Y)


def __connect_offices_by_walls(_offices_assigned2walls):
    def __extract_sub_zones(axis, box, offices):
        _minx, _miny, _maxx, _maxy = box.bounds

        if axis.endswith('y'):
            points4cuts = set(chain.from_iterable([[office.bounds[0], office.bounds[2]] for office in offices]))
            cuts = [LineString([Point(x, _miny), Point(x, _maxy)]) for x in points4cuts]
        else:
            points4cuts = set(chain.from_iterable([[office.bounds[1], office.bounds[3]] for office in offices]))
            cuts = [LineString([Point(_minx, y), Point(_maxx, y)]) for y in points4cuts]
        
        cutted_sub_zones = list(split(box, MultiLineString(cuts)).geoms)
        _overlaped_with_offices = lambda zone, offices=offices: any(zone.intersection(office).area > 0 
                                                                    for office in offices)
        
        sub_zones_inside_box = [zone for zone in cutted_sub_zones if not _overlaped_with_offices]
        return sub_zones_inside_box


    connected_offices_by_walls = {}
    sub_zones_inside_boxes = defaultdict(list)
    
    for axis, offices in _offices_assigned2walls.items():
        box = envelope(GeometryCollection(offices))
        connected_offices_by_walls[axis] = box

        # diff = difference(box, offices)
        # for part in diff:
        #     if not part.is_empty:
        #         sub_zones_inside[axis].append(part)

        # sub_zones_inside_box = __extract_sub_zones(axis, box, offices)
        # if all(not zone.is_empty for zone in sub_zones_inside_box):
        #     sub_zones_inside_boxes[axis] += sub_zones_inside_box
    return connected_offices_by_walls, sub_zones_inside_boxes

def __intersects_with_boundary_walls(office, boundary_walls, wall_width=70):
    resulting_boundary_walls = []
    for axis, line in boundary_walls.items():
        if line.intersection(office).length > wall_width/2:
            resulting_boundary_walls.append((axis, line))
    return resulting_boundary_walls


def _determine_axis_for_zone_at_corner(zone, other_connected_zones_by_walls, boundary_walls):
    intersected_boundary_walls = __intersects_with_boundary_walls(zone, boundary_walls)
    # walls_to_connect = [(__getXY(zone)[1], __getXY(other_connected_zones_by_walls[axis])[1] if axis in other_connected_zones_by_walls.keys() else 0) if axis[1].endswith('y') else
    #                     (__getXY(zone)[0], __getXY(other_connected_zones_by_walls[axis])[0] if axis in other_connected_zones_by_walls.keys() else 0) for axis, _ in intersected_boundary_walls]
    # gaps = [abs(length - _length) for length, _length in walls_to_connect]
    # index_of_min_gap = [i for i, (length, _length) in enumerate(walls_to_connect) if abs(length - _length) == min(gaps)][0]
    # axis, _ = intersected_boundary_walls[index_of_min_gap]

    walls_with_zones_connected = [wall for wall, _ in intersected_boundary_walls if wall in other_connected_zones_by_walls.keys() ]
    walls_with_nothing = list(set(wall for wall, _ in intersected_boundary_walls) - set(walls_with_zones_connected))
    
    min_gap, wall_with_min_gap = (None, None)
    _get_wall_to_connect = lambda zone, axis: __getXY(zone)[1] if axis.endswith('y') else __getXY(zone)[0]
    for wall in walls_with_zones_connected:
        _, axis = wall
        if wall in other_connected_zones_by_walls.keys():
            gap = abs(_get_wall_to_connect(zone, axis) - _get_wall_to_connect(other_connected_zones_by_walls[wall], axis))

        if gap == 0:
            min_gap, wall_with_min_gap = (gap, wall)
            break

    for wall in walls_with_nothing:
        _, axis = wall
        gap = _get_wall_to_connect(zone, axis)
        if min_gap is None or min_gap > gap:
            min_gap, wall_with_min_gap = (gap, wall)
    return wall_with_min_gap


def extract_remained_zones_alongside_offices(connected_offices_by_walls, boundary, axises_in_sequence=['-y', '+x', '+y', '-x']):
    remained_zones_alongside_axises = {}

    max_boxes_by_at_axises = {}
    minx, miny, maxx, maxy = boundary.bounds
    _connected_offices_by_walls = {wall_in_prior: connected_offices_by_walls[wall_in_prior] for wall_in_prior in axises_in_sequence if wall_in_prior in connected_offices_by_walls.keys()}
    for axis, connected_office in _connected_offices_by_walls.items():
        if axis.endswith('y'):
            y = miny if axis.startswith('-') else maxy
            boundary_at_axis = LineString([Point(minx, y), Point(maxx, y)])
        else:
            x = minx if axis.startswith('-') else maxx
            boundary_at_axis = LineString([Point(x, miny), Point(x, maxy)])
        max_box = envelope(GeometryCollection([connected_office, boundary_at_axis]))

        # if axis.endswith('x') and '-y' in max_boxes_by_at_axises.keys():
        #     max_box = difference(max_box, max_boxes_by_at_axises['-y'])
        # elif axis == '+y':
        #     for _axis in ['-x', '+x']:
        #         if _axis in max_boxes_by_at_axises.keys():
        #             max_box = difference(max_box, max_boxes_by_at_axises[_axis])
        
        diff = difference(max_box, connected_office)
        if type(diff) == MultiPolygon:
            remained_zones_alongside_axises[axis] = list(diff.geoms)
        elif type(diff) == Polygon:
            remained_zones_alongside_axises[axis] = [diff]
        max_boxes_by_at_axises[axis] = max_box

    __get_intersected_axises = lambda axis: ['-x', '+x'] if axis.endswith('y') else ['-y', '+y']
    def _reduce_overlaped_offices(axis, zone, _connected_offices_by_walls): 
        reduced_zone = deepcopy(zone)

        # for intersected_axis in __get_intersected_axises(axis):
        #     if intersected_axis in _connected_offices_by_walls.keys() and reduced_zone.intersects(_connected_offices_by_walls[intersected_axis]):
        #         reduced_zone = difference(reduced_zone, _connected_offices_by_walls[intersected_axis])
        #         if not reduced_zone.is_empty and len(reduced_zone.exterior.coords) > 4:
        #             reduced_zone = None
        #         # reduced_zone = None
        #         # # to avoid slim L-type tiles
        #         break

        connected_offices_intersected_with_axis = [connected_office for _axis in __get_intersected_axises(axis)
                                                   for key, connected_office in _connected_offices_by_walls.items()
                                                   if key == _axis]
       
        xs4cuts = [[office.bounds[0], office.bounds[2]] for office in connected_offices_intersected_with_axis]
        ys4cuts = [[office.bounds[1], office.bounds[3]] for office in connected_offices_intersected_with_axis]
        if axis.endswith('y'):
            xs4cuts = list(set(chain.from_iterable(xs4cuts)))

            ys4cuts = list(chain.from_iterable(ys4cuts)) + [zone.bounds[1], zone.bounds[3]]
            _miny, _maxy = [min(ys4cuts), max(ys4cuts)]

            cuts = [LineString([Point(x, _miny), Point(x, _maxy)]) for x in xs4cuts]
        else:
            ys4cuts = list(set(chain.from_iterable(ys4cuts)))

            xs4cuts = list(chain.from_iterable(xs4cuts)) + [zone.bounds[0], zone.bounds[2]]
            _minx, _maxx = [min(xs4cuts), max(xs4cuts)]
            
            cuts = [LineString([Point(_minx, y), Point(_maxx, y)]) for y in ys4cuts]

        zones_cutted = split(zone, MultiLineString(cuts)).geoms
        zones_reduced = [zone for zone in zones_cutted if all(intersected_office.intersection(zone).area == 0
                                                              for intersected_office in connected_offices_intersected_with_axis)]
        reduced_zone = zones_reduced[0] if zones_reduced else None
        return reduced_zone
    
    reduced_zones = defaultdict(list)
    for axis, zones in remained_zones_alongside_axises.items():
        for zone in zones:
            reduced_zone = _reduce_overlaped_offices(axis, zone, _connected_offices_by_walls)
            if reduced_zone is None: continue
            reduced_zones[axis].append(reduced_zone)


    def _remove_intersection_of_reduced_zones(curr_axis, next_axis, reduced_zones):
        if not (curr_axis in reduced_zones.keys() and next_axis in reduced_zones.keys()):
            return 
        
        len0, len1 = len(reduced_zones[curr_axis]), len(reduced_zones[next_axis])
        for i in range(len0):
            for j in range(len1):
                if reduced_zones[curr_axis][i].intersects(reduced_zones[next_axis][j]):
                    intersection = reduced_zones[curr_axis][i].intersection(reduced_zones[next_axis][j])

                    connected_reduced_zones = {key: envelope(GeometryCollection(values)) for key, values in reduced_zones.items()}
                    axis = _determine_axis_for_zone_at_corner(intersection, connected_reduced_zones, boundary_walls)
                    if axis != curr_axis:
                        reduced_zones[curr_axis][i] = difference(reduced_zones[curr_axis][i], intersection)
                    if axis != next_axis:
                        reduced_zones[next_axis][j] = difference(reduced_zones[next_axis][j], intersection)
                    return
    
    boundary_walls = _get_walls(*boundary.bounds)
    for curr_axis, next_axis in zip(axises_in_sequence, axises_in_sequence[1:] + axises_in_sequence[:1]):
        _remove_intersection_of_reduced_zones(curr_axis, next_axis, reduced_zones)

    return max_boxes_by_at_axises, reduced_zones



def extract_main_zone_by_max_boxes(max_boxes_by_at_axises, boundary):
    remained_zone = deepcopy(boundary)
    for _, max_box in max_boxes_by_at_axises.items():
        remained_zone = difference(remained_zone, max_box)
    return remained_zone


def _adapt_a_zone(zone):
    minx, miny, maxx, maxy = zone.bounds
    origin = (minx, miny)
    rect = (maxx - minx, maxy - miny)
    return (origin, rect)