import math

from shapely.geometry import LineString, Point, GeometryCollection
from shapely import envelope

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from zone_identification.utils_for_zone_identification import _get_walls, _adapt_a_zone
from rotate_back_new_by_yifei import rotate_back_new


def _rotate_layout(rotation, path_segs, main_door, counterclock_axises=['-y', '+x', '+y', '-x']):
    # i = 0
    # if rotation == -90:
    #     i = -1
    # elif rotation == 90:
    #     i = 1
    # elif rotation == 180:
    #     i = 2
    # else:
    #     i = 0
    # rotated_axises = counterclock_axises[i:] + counterclock_axises[:i]
    # rotation_map = dict(zip(counterclock_axises, rotated_axises))
    # rotated_boundaries = {rotation_map[axis]: wall_line for axis, wall_line in boundaries.items()}

    # rotated_pathSegs = dict([(LineString([Point(*rotated_point) for rotated_point in rotate_back_new(line.coords, math.radians(rotation))]), _type) for line, _type in pathSegs.items()])
    _rotation = math.radians(rotation)
    rotated_path_segs = [(rotate_back_new(points, _rotation), _type) for points, _type in path_segs]
    rotated_main_door = rotate_back_new([main_door], _rotation)[0] if main_door else main_door
    return rotated_path_segs, rotated_main_door


def _identify_boundaries4region(_path_segs, wall_types=['existWall', 'solidWall', 'halfGlassWall', 'glassWall', 'virtualWall']):
    wall_map = {wall_type: 'virtual_wall4local_layout' if wall_type == 'virtualWall' else \
                            'office_wall' if wall_type == 'halfGlassWall' or wall_type == 'glassWall' else \
                                'wall'
                for wall_type in wall_types}
    
    # path_segs = dict([(LineString([Point(int(pathSeg[vertex]['x']), int(pathSeg[vertex]['y'])) for vertex in ['start', 'end']]), pathSeg['type']) 
    #                   for pathSeg in pathSegs])
    path_segs = dict([(LineString([(int(x), int(y)) for x, y in points]), _type) for points, _type in _path_segs])
    region = envelope(GeometryCollection(list(path_segs.keys())))
    # workspace = envelope(LineString([Point(0, 0), Point(maxx - minx, maxy - miny)]))

    region_walls = _get_walls(*region.bounds)
    _find_wall_axis = lambda wall_line, region_walls=region_walls: [axis for axis, workspace_wall in region_walls.items() if workspace_wall.intersection(wall_line).length > 0]
    boundaries = {}
    for pathSeg, pathType in path_segs.items():
        # _pathSeg = LineString([Point(x - minx, y - miny) for x, y in pathSeg.coords])
        _pathSeg = LineString(sorted(pathSeg.coords, key=lambda coord: (coord[0], coord[1])))
        axises = _find_wall_axis(_pathSeg)
        if axises:
            axis = axises[0]
            boundaries[axis] = (wall_map[pathType], _pathSeg, False)

    return boundaries, region_walls, region


def identify_region(baseMessage):    
    path_segs = [([(path_seg[vertex]['x'], path_seg[vertex]['y']) for vertex in ['start', 'end']],
                    path_seg['type'])
                 for path_seg in baseMessage['pathSegs']]
    boundaries, region_walls, region = _identify_boundaries4region(path_segs)

    if baseMessage['doorWindowDatas']:
        main_door = baseMessage['doorWindowDatas'][0]
        main_door = (int(main_door['center']['x']), int(main_door['center']['y']))
    else:
        main_door = None

    if boundaries['+y'][0] == 'virtual_wall4local_layout':
        wall4plusY, max_dist2main_door = None, None
        for axis, (wall_type, wall_line) in boundaries.items():
            if axis == '+y' or  wall_type == 'island': continue

            if main_door:
                dist2door = wall_line.distance(Point(*main_door))
            else:
                dist2door = wall_line.length
            if dist2door == 0: continue
            
            if max_dist2main_door is None or max_dist2main_door < dist2door:
                wall4plusY, max_dist2main_door = axis, dist2door
    else:
        wall4plusY = '+y'

    rotation_map = {'+y': 0, '-x': 90, '-y': 180, '+x': -90}
    if wall4plusY != '+y':
        rotation = rotation_map[wall4plusY]
        
        path_segs, main_door = _rotate_layout(rotation, path_segs, main_door)
        boundaries, region_walls, region = _identify_boundaries4region(path_segs)
    else:
        rotation = 0


    boundary_against_in_Y_axis4main_zone, boundary_against4main_zone = [[boundaries[axis] if axis in boundaries.keys() else ('wall', region_walls[axis]) for axis in axises]
                                                                          for axises in [['-y', '+y'], ['-x', '+x']]]
    return rotation, main_door, (boundary_against_in_Y_axis4main_zone, boundary_against4main_zone), region

