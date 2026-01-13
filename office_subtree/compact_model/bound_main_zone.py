import math
from copy import deepcopy
from shapely.geometry import LineString, Point, MultiLineString
from shapely import envelope
from shapely.ops import split
from itertools import chain
from collections import defaultdict

from .transform import transform_RECTs, transform_components
from .unfold_RECTs_into_rows import unfold_RECTs_in_main_zone, _yield_rects4subjects, unfold_RECTs_in_partitions
from .unfold_rows_into_components import unfold_components_in_main_zone, unfold_components_in_sub_zone, \
                                            unfold_components_in_main_zone_for_local_layout, __unfold_a_partitioned_row_of_printer_sets
from .bound_sub_model import __get_uniform_distribution, _place_printer_sets_in_XY_axises, \
                            _place_storage_in_partitioned_zones, _bound_in_storage_placements, __sum_up, \
                            _get_spacing_between
from .calcu_spacing_within_main_zone import _determine_zone_for_intersected_placements, _determine_neighbors_for_zone_in_X_axis,\
                                            _calcu_remained_wall_in_X_axis, __calcu_maxY_in_X_axis
from .builtin import __combine_multiple_defaultdictlists

from .plmt_utils import __get_spacing_for_each_boundary
from ._place_components_within_main_zone_for_local_layout import _place_components_within_main_zone_for_local_layout

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from general.configs import spacing, sizes, rotations_of_directions
from general.latest_spacing import spacing as latest_spacing, main_passageway_width, additional_passageway_width, \
                                    __map_side_to_index, wall_width
from general.utils import _calcu_occupied_length_for_subjects, _calcu_nrows4subjects



def _get_subject_near_boundaries(partial_individual):
    num_of_two_col_islands, num_of_two_col_low_cabinets, has_mixed_cabinets_island = partial_individual

    subject_on_left, subject_on_right = None, None
    left2right = [num_of_two_col_low_cabinets, has_mixed_cabinets_island, num_of_two_col_islands]
    left2right_subjects = ['low_cabinet', 'low_cabinet', 'desk']
    for num, subject in zip(left2right, left2right_subjects):
        if num > 0:
            subject_on_left = subject
            break
    right2left_subjects = ['desk', 'desk', 'low_cabinet']
    for num, subject in zip(left2right[::-1], right2left_subjects):
        if num > 0:
            subject_on_right = subject
            break
    return subject_on_left, subject_on_right


def __with_door_alongside_wall(axis, wall_line, main_door):
    if wall_line and main_door:
        minx, miny, maxx, maxy = wall_line.bounds
        half_wall_width = wall_width / 2
        wall = envelope(LineString([Point(minx, miny - half_wall_width), Point(maxx, maxy + half_wall_width)])) if axis == 'X' else \
                envelope(LineString([Point(minx - half_wall_width, miny), Point(maxx + half_wall_width, maxy)]))
        return wall.intersects(Point(*main_door))
    else:
        return False
        
def __get_walls4main_zone(boundary_against_in_Y_axis4main_zone, boundary_against4main_zone, relative_main_door=None, 
                          wall_width=wall_width, check_existense_of_walls=True):
    # with_door_alongside_wall = lambda wall_line, main_door: wall_line.intersects(Point(*main_door)) if main_door else False

    boundary_againsts = boundary_against_in_Y_axis4main_zone + boundary_against4main_zone
    corresponding_axises = ['X'] * 2 + ['Y'] * 2
    corresponding_walls = ['down', 'up', 'left', 'right']
    _check_boundary_func = lambda boundary_against, check_existense_of_walls=check_existense_of_walls: boundary_against == 'wall' if check_existense_of_walls else True
    walls4main_zones = [(boundary_against, axis, wall, wall_line, __with_door_alongside_wall(axis, wall_line, relative_main_door)) for (boundary_against, wall_line, _), axis, wall in zip(boundary_againsts, corresponding_axises, corresponding_walls) 
                        if _check_boundary_func(boundary_against)]
    return walls4main_zones


def __split_zone_by_door_both_in_X_axis(door_center, zone, zone_boundary_against,
                                        door_width=main_passageway_width):
    (x, y), (X, Y) = zone
    rect = envelope(LineString([Point(x, y), Point(x + X, y + Y)]))

    d_x, d_y = door_center
    startX, endX = [d_x - door_width / 2, d_x + door_width / 2]
    door_lines = MultiLineString([LineString([Point(x, y), Point(x, y + Y)]) for x in [startX, endX]])

    splitted_zones = []
    boundary_against4zones = []
    for splitted_zone in split(rect, door_lines).geoms:
        _rough_door = envelope(door_lines)

        if splitted_zone.intersection(_rough_door).area > 0: continue


        minx, miny, maxx, maxy = splitted_zone.bounds
        rect = ((minx, miny), (maxx - minx, maxy - miny))
        splitted_zones.append(rect)

        _boundary_against = list(zone_boundary_against)
        zone_lines = [LineString([Point(x, y), Point(x, y + Y)]) for x in [minx, maxx]]
        for zone_line, index in zip(zone_lines, range(2)):
            if zone_line.intersects(_rough_door):
                _boundary_against[index] = ('door', False)
        boundary_against4zones.append(tuple(_boundary_against))
    return splitted_zones, boundary_against4zones


def __sort_placement_by_walls(walls4main_zone, num_of_storage_in_axises, num_of_printer_sets_in_axises,
                                priorities4walls={'down': 0, 'left': 1, 'right': 2, 'up': 3}):
    nsteps = 6
    _num_of_storage_in_axises = [tuple(num_of_storage_in_axises[nsteps*j:nsteps*j+nsteps]) for j in range(len(walls4main_zone))]
    _available_walls_dict = {wall: [wall_line, with_door_alongside_wall,  *nums] for (*_, wall, wall_line, with_door_alongside_wall), *nums in zip(walls4main_zone, num_of_printer_sets_in_axises, _num_of_storage_in_axises)}
    # plmts_of_printer_sets_and_storage_in_axises = dict(zip(available_walls, num_of_printer_sets_in_axises, _num_of_storage_in_axises))
    _available_walls_in_priority = dict(sorted(_available_walls_dict.items(), key=lambda item: priorities4walls[item[0]]))
    return _available_walls_in_priority


def _place_printer_sets_and_storage_near_walls(num_of_storage_in_axises, num_of_printer_sets_in_axises, comp_upbounds,
                                                boundary_against_in_Y_axises, boundary_against,
                                                relative_main_zone, walls_of_boundary_againsts=['down', 'up', 'left', 'right'],
                                                relative_main_door=None):
    num_of_printer_sets_near_walls = {}
    num4storage_near_walls = {}
    updated_relative_main_zone = deepcopy(relative_main_zone)
    _boundary_against4updated_main_zone = [tuple(_boundary_against) for *_boundary_against, _ in boundary_against_in_Y_axises]
    _boundary_against_in_Y_axis4updated_main_zone = [tuple(_boundary_against) for *_boundary_against, _ in boundary_against]
    relative_plmts4printer_sets_and_storage = defaultdict(list)
    overbounds_of_parallel2x4storage, overbounds_of_storage, overbounds_of_printer_sets = 0, 0, 0


    # _boundary_againsts = boundary_against_in_Y_axises + (list(boundary_against) if type(boundary_against) is tuple else boundary_against)
    # corresponding_walls = ['down', 'up'] + ['left', 'right']
    # available_walls = [(wall, wall_line) for wall, (boundary_against, wall_line) in zip(corresponding_walls, _boundary_againsts) if boundary_against == 'wall']
    available_walls = __get_walls4main_zone(boundary_against_in_Y_axises, boundary_against, relative_main_door=relative_main_door)
    if not available_walls:
        return num_of_printer_sets_near_walls, relative_plmts4printer_sets_and_storage, updated_relative_main_zone, \
                _boundary_against_in_Y_axis4updated_main_zone, _boundary_against4updated_main_zone, \
                overbounds_of_parallel2x4storage, overbounds_of_storage, overbounds_of_printer_sets

    _boundaries = [(wall, with_door) for wall, _, _, wall_line, with_door in __get_walls4main_zone(boundary_against_in_Y_axises, boundary_against, relative_main_door=relative_main_door, check_existense_of_walls=False)]
    _boundary_against_in_Y_axis4updated_main_zone, _boundary_against4updated_main_zone = _boundaries[:2], _boundaries[2:]

    _available_walls_in_priority = __sort_placement_by_walls(available_walls, num_of_storage_in_axises, num_of_printer_sets_in_axises)
    remained_walls_in_X_axis = {}
    maxYs_in_X_axis = {wall: (0, ('wall', False if wall in ['down', 'up'] else True)) for wall in walls_of_boundary_againsts}
    for wall, (wall_line, with_door_alongside_wall, _num_of_printer_sets_in_axis, _num_of_storage_in_axis) in _available_walls_in_priority.items():
    # for wall, _num_of_printer_sets_in_axis, _num_of_storage_in_axis in zip(_available_walls_in_priority.keys(), num_of_printer_sets_in_axises, _num_of_storage_in_axises):
        # if boundary_against != 'wall' and num4printer_sets > 0:
        #     overbounds_of_printer_sets = 1

        relative_num4storage_in_X_axis = _num_of_storage_in_axis if wall in ['down', 'up'] else \
                                                [not value if i % 3 == 0 else value for i, value in enumerate(_num_of_storage_in_axis)]

        (maxY_in_X_axis, component_with_maxY), shifted_zone4both = _determine_zone_for_intersected_placements(wall, relative_num4storage_in_X_axis, _num_of_printer_sets_in_axis, 
                                                                                                            remained_walls_in_X_axis, maxYs_in_X_axis, 
                                                                                                            updated_relative_main_zone, relative_main_zone)
        # maxYs_in_X_axis[wall] = (maxY_in_X_axis, component_with_maxY)
        # subject, parallel2x = component_with_maxY
        # if maxY_in_X_axis > 0:
        #     new_boundary = (subject, parallel2x if wall in ['down', 'up'] else not parallel2x)
        # else:
        #     new_boundary = ('wall', False)
        # maxYs_in_X_axis[wall] = (maxY_in_X_axis, new_boundary)

        _updated_neighbors_in_X_axis = _boundary_against4updated_main_zone if wall in ['down', 'up'] else _boundary_against_in_Y_axis4updated_main_zone
        neighbors4shifted_zone = _determine_neighbors_for_zone_in_X_axis(wall, maxY_in_X_axis, component_with_maxY, 
                                                                        remained_walls_in_X_axis, maxYs_in_X_axis, neighbors=_updated_neighbors_in_X_axis)
        if wall in ['down', 'up']:
            _relative_boundary_against4zone_in_X_axis = neighbors4shifted_zone
        else:
            _relative_boundary_against4zone_in_X_axis = [(component, not parallel2x) for component, parallel2x in neighbors4shifted_zone]
        
        (x, y), (X, Y) = shifted_zone4both
        relative_origin = (0, 0)

        # wall_line = _available_walls_dict[wall]
        start_point, end_point = list(wall_line.coords)
        w_x, w_y = start_point
        if wall in ['down', 'up']:
            if wall == 'down' and wall_line.length < X:
                relative_origin = (w_x - x, 0)
                X = wall_line.length
            relative_shifted_zone4both_in_X_axis = (relative_origin, (X, Y))
            relative_num4storage_in_X_axis = _num_of_storage_in_axis

            if with_door_alongside_wall:
                d_x, d_y = relative_main_door
                relative_main_door_in_X_axis = (d_x - x, d_y - y)
        elif wall in ['left', 'right']:
            if wall_line.length < Y:
                relative_origin = (w_y - y, 0)
                Y = wall_line.length
            relative_shifted_zone4both_in_X_axis = (relative_origin, (Y, X))
            relative_num4storage_in_X_axis = [not value if i % 3 == 0 else value for i, value in enumerate(_num_of_storage_in_axis)]

            if with_door_alongside_wall:
                d_x, d_y = relative_main_door
                relative_main_door_in_X_axis = (d_y - y, d_x - x)


        if with_door_alongside_wall:
            splitted_zones, boundary_against4zones = __split_zone_by_door_both_in_X_axis(relative_main_door_in_X_axis, relative_shifted_zone4both_in_X_axis, tuple(_relative_boundary_against4zone_in_X_axis))
        else:
            splitted_zones, boundary_against4zones = [relative_shifted_zone4both_in_X_axis], [tuple(_relative_boundary_against4zone_in_X_axis)]


        nums4printer_sets_in_X_axis = []
        plmts4storage_in_X_axis = []
        plmt_results4partitioned_zones = []

        plmt4printer_sets_in_X_axis = (True, _num_of_printer_sets_in_axis)
        _remained_plmt4printer_sets_in_X_axis = list(plmt4printer_sets_in_X_axis)
        _remained_num4storage_in_X_axis = deepcopy(relative_num4storage_in_X_axis)
        for splitted_zone, boundary_against4zone in zip(splitted_zones, boundary_against4zones):
            _num_of_printer_sets, rectangles4printer_sets, partitioned_zones, boundary_against4partitioned_zones = _place_printer_sets_in_XY_axises(splitted_zone, _remained_plmt4printer_sets_in_X_axis,
                                                                                                                                                    _default_boundary_against=boundary_against4zone)
            _summed_plmts, plmts_in_partitions, RECTs_in_partitions, remained_plmts = _place_storage_in_partitioned_zones(_remained_num4storage_in_X_axis, partitioned_zones, boundary_against4partitioned_zones,
                                                                                                                          _boundary_against_in_Y_axis4main_zone=_boundary_against_in_Y_axis4updated_main_zone)
            plmt_results4partitioned_zones += [(splitted_zone, 
                                                rectangles4printer_sets, partitioned_zones, boundary_against4partitioned_zones,
                                                _summed_plmts, plmts_in_partitions, RECTs_in_partitions)]
            nums4printer_sets_in_X_axis.append(_num_of_printer_sets)
            plmts4storage_in_X_axis.append(_summed_plmts)
            _remained_plmt4printer_sets_in_X_axis[1] -= _num_of_printer_sets
            _remained_num4storage_in_X_axis = list(chain.from_iterable([remained_plmts[subject] for subject in ['big_lockers', 'high_cabinets'] if subject in remained_plmts.keys()]))
        
        total_num_of_printer_sets_in_X_axis = sum(nums4printer_sets_in_X_axis)
        k, delta = 0, 3
        relative_plmts_in_X_axis = {subject : list(relative_num4storage_in_X_axis[delta*i:delta*i+delta]) for i, subject in enumerate(['big_lockers', 'high_cabinets'])}
        total_plmts4storage_in_X_axis = {subject: __sum_up(subject, *plmt, plmts4storage_in_X_axis) for subject, plmt in relative_plmts_in_X_axis.items()}
        _total_plmts4storage_in_X_axis = tuple([total_plmts4storage_in_X_axis[subject] for subject in ['big_lockers', 'high_cabinets']])
        # relative_plmts4printer_sets_and_storage[(wall, shifted_zone4both, total_num_of_printer_sets_in_X_axis, _total_plmts4storage_in_X_axis)] = plmt_results4partitioned_zones

        num_of_printer_sets_near_walls[wall] = total_num_of_printer_sets_in_X_axis

        (maxY_in_X_axis, component_with_maxY), (minY_in_X_axis, _) = [__calcu_maxY_in_X_axis(list(chain.from_iterable(_total_plmts4storage_in_X_axis)), total_num_of_printer_sets_in_X_axis, max_or_min=max_or_min) for max_or_min in [max, min]]
        subject, parallel2x = component_with_maxY
        if maxY_in_X_axis > 0:
            new_neighbor = (subject, parallel2x if wall in ['down', 'up'] else not parallel2x)
        else:
            new_neighbor = ('wall', with_door_alongside_wall)
        maxYs_in_X_axis[wall] = (maxY_in_X_axis, new_neighbor)

        def __get_restricted_zone(zone, maxY_in_X_axis):
            origin, (X, Y) = zone
            return (origin, (X, maxY_in_X_axis))
        _plmt_results4partitioned_zones = [(splitted_zone, rectangles4printer_sets, [__get_restricted_zone(zone, maxY_in_X_axis) for zone in partitioned_zones], *values) 
                                            for splitted_zone, rectangles4printer_sets, partitioned_zones, *values in plmt_results4partitioned_zones]
        relative_plmts4printer_sets_and_storage[(wall, shifted_zone4both, total_num_of_printer_sets_in_X_axis, _total_plmts4storage_in_X_axis, (maxY_in_X_axis, minY_in_X_axis))] = _plmt_results4partitioned_zones

        # plmt4printer_sets = (1, _num_of_printer_sets_in_axis)
        # num_of_printer_sets, *relative_plmt_results4printer_sets, boundary_against4partitioned_zones = _place_printer_sets_in_XY_axises(relative_shifted_zone4both_in_X_axis, plmt4printer_sets,
        #                                                                                                            _default_boundary_against=_relative_boundary_against4zone_in_X_axis)
        # relative_plmts, *relative_plmt_results4storage, remained_plmts = _place_storage_in_partitioned_zones(relative_num4storage_in_X_axis, relative_plmt_results4printer_sets[1], boundary_against4partitioned_zones)
        # relative_plmts4printer_sets_and_storage[wall] = (shifted_zone4both,
        #                                                  (relative_shifted_zone4both_in_X_axis, relative_plmt_results4printer_sets, boundary_against4partitioned_zones,
        #                                                  relative_num4storage_in_X_axis, relative_plmt_results4storage))

        # overbounds_of_parallel2x4storage = 1 if any(not value if i % 3 == 0 else value for i, value in enumerate(relative_num4storage_in_X_axis)) else 0
        # # _upbound4storage = comp_upbounds['in_X_axis'] if wall == 'down' else comp_upbounds['in_Y_axis']
        # # overbounds_of_storage = _bound_in_storage_placements(relative_plmts, _upbound4storage, remained_plmts)
        # # if boundary_against != 'wall' and any(nrows * ncols != 0 for _, nrows, ncols in relative_plmts.values()):
        # #     overbounds_of_storage = 1

        # # overbounds_in_parallel2x4storage = 1 if any(parallel2x != 1 for parallel2x, *_ in relative_plmts.values()) else 0


        # remained_walls_in_X_axis[wall] = _calcu_remained_wall_in_X_axis(_num_of_printer_sets_in_axis, relative_plmt_results4printer_sets,
        #                                                                 relative_num4storage_in_X_axis, relative_plmt_results4storage,
        #                                                                 relative_shifted_zone4both_in_X_axis)
        # num_of_printer_sets_near_walls[wall] = num_of_printer_sets


        maxY4both, new_neighbor = maxYs_in_X_axis[wall]

        # l, w = sizes['storage']
        # Ys4storage_in_X_axis = {(comp, parallel2x): 0 if nrows * ncols == 0 else _calcu_occupied_length_for_subjects(comp, nrows, w, near_wall=True) if parallel2x else l * ncols 
        #                         for comp, (parallel2x, nrows, ncols) in relative_plmts.items()}
        # maxY4storage_in_X_axis = max(Ys4storage_in_X_axis.values())
        # _, (X, Y) = relative_shifted_zone4both_in_X_axis
        # if maxY4storage_in_X_axis > Y:
        #     overbounds_of_storage = 1

        # l, w = sizes['printer_set']
        # if l > X or w > Y:
        #     overbounds_of_printer_sets = 1
        # maxY4both = max(maxY4storage_in_X_axis, w if _num_of_printer_sets_in_axis > 0 else 0)
        # if maxY4both > 0:
        #     Ys_in_X_axis = deepcopy(Ys4storage_in_X_axis)
        #     Ys_in_X_axis[('printer_set', True)] = w if _num_of_printer_sets_in_axis > 0 else 0
        #     _new_neighbor = [key for key, Y in Ys_in_X_axis.items() if Y == maxY4both][0]
        #     neighbor, parallel2x = _new_neighbor
        #     new_neighbor = (neighbor, parallel2x if wall in ['down', 'up'] else not parallel2x)

        #     (x, y), (X, Y) = updated_relative_main_zone
        #     # new_neighbor = ('printer_set', None) if maxY4both == w else ('storage', None)
        if maxY4both:
            (x, y), (X, Y) = updated_relative_main_zone

            down_neighbor, up_neighbor = _boundary_against_in_Y_axis4updated_main_zone
            left_neighbor, right_neighbor = _boundary_against4updated_main_zone
            if wall == 'down':
                updated_relative_main_zone = ((x, y + maxY4both), (X, Y - maxY4both))
                _boundary_against_in_Y_axis4updated_main_zone = (new_neighbor, up_neighbor)
                # for key in ['left', 'right']:
                #     if key in _available_walls_in_priority.keys():
                #         wall_line = _available_walls_in_priority[key]
                #         start_point, end_point = list(wall_line.coords)
                #         x, y = start_point
                #         _available_walls_in_priority[key][0] = LineString([Point(x, y + maxY4both), Point(*end_point)])
            elif wall == 'up':
                updated_relative_main_zone = ((x, y), (X, Y - maxY4both))
                _boundary_against_in_Y_axis4updated_main_zone = (down_neighbor, new_neighbor)
            elif wall == 'left':
                updated_relative_main_zone = ((x + maxY4both, y), (X - maxY4both, Y))
                _boundary_against4updated_main_zone = (new_neighbor, right_neighbor)
            elif wall == 'right':
                updated_relative_main_zone = ((x, y), (X - maxY4both, Y))
                _boundary_against4updated_main_zone = (left_neighbor, new_neighbor)

    # assert relative_plmts4printer_sets_and_storage.keys() == _available_walls_in_priority.keys()
    return num_of_printer_sets_near_walls, relative_plmts4printer_sets_and_storage, updated_relative_main_zone, _boundary_against_in_Y_axis4updated_main_zone, _boundary_against4updated_main_zone, \
            overbounds_of_parallel2x4storage, overbounds_of_storage, overbounds_of_printer_sets


def _place_accompany_seats(num_of_accompaniment_seats, num_of_available_seats, 
                           rangeX4accompaniment_seats, 
                           up_spacing, updated_relative_main_zone, 
                           user_desk=None, user_desk_spacing=None, latest_spacing=latest_spacing):
    rectangles4accompaniment_seats = []
        
    startX, endX = rangeX4accompaniment_seats
    if not startX and not endX:
        return rectangles4accompaniment_seats
    
    # l, w = sizes['desk']
    l, w = user_desk if user_desk else sizes['desk']

    _longside_index = __map_side_to_index('longside')
    _shortside_index = __map_side_to_index('shortside')
    user_desk_spacing = user_desk_spacing if user_desk_spacing else latest_spacing['desk']['against_desk'][_longside_index][_longside_index]
    accompaniment_seat_spacing = latest_spacing['accompany_seat']['against_accompany_seat'][_shortside_index][_shortside_index]

    if num_of_accompaniment_seats <= num_of_available_seats:
        # self_spacing = user_desk_spacing + w*2 - l
        # if num_of_accompaniment_seats > 1:
        #     mean_units = (num_of_available_seats - num_of_accompaniment_seats) / (num_of_accompaniment_seats - 1)
        #     if mean_units >= 1:
        #         self_spacing = math.ceil(mean_units) * (self_spacing + w*2) - l

        shift4startX = (l - w * 2) / 2
        startX -= shift4startX
        self_spacing = user_desk_spacing - shift4startX * 2
    else:
        self_spacing = accompaniment_seat_spacing
        if num_of_accompaniment_seats > 1:
            mean_spacing = int((endX - startX - num_of_accompaniment_seats * l) / (num_of_accompaniment_seats - 1))
            if mean_spacing > self_spacing:
                self_spacing = mean_spacing

    relative_origin, (X, Y) = updated_relative_main_zone
    y = relative_origin[1] + Y - up_spacing - w
    for j in range(num_of_accompaniment_seats):
        x = startX + (l + self_spacing) * j 
        if x + l <= endX: 
            rectangles4accompaniment_seats.append(((x, y), (l, w)))
    return rectangles4accompaniment_seats


def _update_num_of_subjects_within_main_zone(num_of_subjects_per_col, rectangles4accompaniment_seats, 
                                             num_of_two_col_islands, RECTs, 
                                             remained_length, length4desks, 
                                             inputs4local_layout=None, 
                                             user_desk=None, user_desk_spacing=None,
                                             latest_spacing=latest_spacing):
    desk_length, desk_width = user_desk if user_desk else sizes['desk']

    def _intersects(RECT_per_col, rectangles4accompaniment_seats=rectangles4accompaniment_seats): 
        (x, y), (X, Y) = RECT_per_col
        _space = spacing['desk']['against_desk']['longside']
        RECT_in_X_axis = LineString([Point(x - _space, 0), Point(x + X + _space, 0)])

        for (x, y), (X, Y) in rectangles4accompaniment_seats:
            seat_in_X_axis = LineString([Point(x, 0), Point(x + X, 0)])
            if RECT_in_X_axis.intersection(seat_in_X_axis).length > 0: return True
        return False

    new_num_of_subjects_per_col = deepcopy(num_of_subjects_per_col)
    
    if RECTs[1] and not inputs4local_layout:
        new_num_of_subjects_per_col['mixed_desk'] = int(remained_length / desk_length)
        new_num_of_subjects_per_col['mixed_cabinet'] = int(remained_length / sizes['storage'][0])
        # num_of_accompaniment_seats -= 1
    if RECTs[-2]:
        self_spacing = user_desk_spacing if user_desk_spacing else latest_spacing['desk']['against_desk'][__map_side_to_index('longside')][__map_side_to_index('longside')]
        rectangles = list(_yield_rects4subjects(RECTs[-2], num_of_two_col_islands,desk_width*2, self_spacing))
        new_num_of_subjects_per_col['desk'] = [int((remained_length if _intersects(RECT_per_col) else length4desks) / desk_length) 
                                                for RECT_per_col in rectangles]
    return new_num_of_subjects_per_col
            
    
def _get_RECTs(RECTs, num_of_subjects_per_col, partial_individual, 
               down_spacing, left_spacing,
               relative_origin=(0, 0), spacing=spacing):
    num_of_two_col_islands, num_of_two_col_low_cabinets, has_mixed_cabinets_island = partial_individual
    # , subject_near_wall, num_of_subjects_near_wall = partial_individual
    
    x, y = relative_origin
    y += down_spacing
    y4islands = y + sizes['storage'][1]

    _get_RECT4mixed = lambda prev_endX, next_spacing, y, num_of_desks_per_col=num_of_subjects_per_col['desk']: (
        (prev_endX + next_spacing, y),
        (sizes['storage'][1] + sizes['desk'][1], sizes['desk'][0] * num_of_desks_per_col)
    )
    _get_RECT4islands = lambda prev_endX, next_spacing, num_of_two_col_islands, y, num_of_desks_per_col=num_of_subjects_per_col['desk']: None if num_of_two_col_islands == 0 else (
        (prev_endX + next_spacing, y),
        (sizes['desk'][1]*2 * num_of_two_col_islands +  spacing['desk']['against_self']['longside'] * (num_of_two_col_islands - 1), sizes['desk'][0] * num_of_desks_per_col)
    )
    _get_RECT4cabinets = lambda prev_endX, next_spacing, num_of_two_col_low_cabinets, y, num_of_cabinets_per_col=num_of_subjects_per_col['cabinet']: (
        (prev_endX + next_spacing, y),
        (sizes['storage'][1]*2 * num_of_two_col_low_cabinets + spacing['cabinet']['against_self']['longside'] * (num_of_two_col_low_cabinets - 1), sizes['storage'][0] * num_of_cabinets_per_col)     # minor
    )
    _get_RECT4subjects_near_wall = lambda prev_endX, next_spacing, subject, num_of_subjects, y, num_of_subjects_per_col=num_of_subjects_per_col: (
        (prev_endX + next_spacing, y),
        (_calcu_occupied_length_for_subjects(subject, num_of_subjects, sizes['storage'][1]), sizes['storage'][0] * num_of_subjects_per_col['cabinet'])
    )
    _get_endX = lambda RECT: sum(RECT[i][0] for i in range(2))

    if num_of_two_col_low_cabinets == 0:
        if has_mixed_cabinets_island == 0:
            RECTs[-2] = _get_RECT4islands(x, left_spacing, num_of_two_col_islands, y4islands)

        else:
            RECTs[1] = _get_RECT4mixed(x, left_spacing, y4islands)
            RECTs[-2] = _get_RECT4islands(_get_endX(RECTs[1]), spacing['desk']['against_self']['longside'], num_of_two_col_islands, y4islands)

    else:
        RECTs[0] = _get_RECT4cabinets(x, left_spacing, num_of_two_col_low_cabinets, y)

        endX = _get_endX(RECTs[0])
        if has_mixed_cabinets_island == 0:
            RECTs[-2] = _get_RECT4islands(endX, spacing['desk']['against_storage']['longside'], num_of_two_col_islands, y4islands)

        else:
            RECTs[1] = _get_RECT4mixed(endX, spacing['cabinet']['against_self']['longside'], y4islands)
            RECTs[-2] = _get_RECT4islands(_get_endX(RECTs[1]), spacing['desk']['against_self']['longside'], num_of_two_col_islands, y4islands)

    # if num_of_subjects_near_wall > 0:
    #     subject = 'big_lockers' if subject_near_wall else 'high_cabinets'
    #     if RECTs[-2]:
    #         prev_endX, next_spacing = _get_endX(RECTs[-2]), spacing['desk']['against_storage']['longside']
    #     elif RECTs[1]:
    #         prev_endX, next_spacing = _get_endX(RECTs[1]), spacing['desk']['against_storage']['longside']
    #     elif RECTs[0]:
    #         prev_endX, next_spacing = _get_endX(RECTs[0]), spacing['cabinet']['against_self']['longside']
    #     else:
    #         prev_endX, next_spacing = x, spacing['storage'][f'against_{left_neighbor}']['longside']
    #     RECTs[-1] = _get_RECT4subjects_near_wall(prev_endX, next_spacing, subject, num_of_subjects_near_wall, y)
        
    return RECTs
    

def _place_components_within_main_zone(partial_individual, main_zone, 
                                       boundary_against4_main_zone, _main_passageways4boundary_against,
                                       up_spacing, down_spacing,
                                       user_desk=None, user_desk_spacing=None, sizes=sizes):
    desk_length, desk_width = user_desk

    num_of_two_col_islands, num_of_two_col_low_cabinets, has_mixed_cabinets_island = partial_individual

    (_, y), (_, Y) = main_zone
    y4desks = y + down_spacing + sizes['storage'][1]
    y4storage = y + down_spacing

    length = Y - up_spacing
    length4desks = length - sizes['storage'][1] - down_spacing
    length4storage = length4desks + sizes['storage'][1]

    def _get_non_empty_boundary(partial_individual):
        num_of_two_col_islands, num_of_two_col_low_cabinets, has_mixed_cabinets_island = partial_individual
        _subjects_in_order = dict(zip(['low_cabinets', 'mixed_island', 'two_col_islands'], 
                                      [num_of_two_col_low_cabinets, has_mixed_cabinets_island, num_of_two_col_islands]))
        
        non_empty_subjects = [subject for subject, num in _subjects_in_order.items() if num > 0]
        first_none_empty, last_none_empty = (non_empty_subjects[0], non_empty_subjects[-1]) if non_empty_subjects else ('', '')
        return first_none_empty, last_none_empty
    
    def _update_partial_individual(subject, new_num, partial_individual):
        num_of_two_col_islands, num_of_two_col_low_cabinets, has_mixed_cabinets_island = partial_individual
        _subjects_in_order = dict(zip(['low_cabinets', 'mixed_island', 'two_col_islands'], 
                                      [num_of_two_col_low_cabinets, has_mixed_cabinets_island, num_of_two_col_islands]))
        _subjects_in_order[subject] = new_num
        return [_subjects_in_order[sub] for sub in ['two_col_islands', 'low_cabinets', 'mixed_island']]
    

    _partial_individual = deepcopy(partial_individual)

    RECTs = {}
    updated_plmts = {}
    remained_BOX = deepcopy(main_zone)
    updated_boundary_against4remained_BOX = list(boundary_against4_main_zone)
    for subject, num_of_subjects in zip(['low_cabinets', 'mixed_island', 'two_col_islands'],
                                            [num_of_two_col_low_cabinets, has_mixed_cabinets_island, num_of_two_col_islands]):
        # left_spacing, right_spacing = [_get_spacing_between(sub_subject, boundary) for sub_subject, boundary in zip([('storage', False)] * 2 if subject == 'low_cabinets' else \
        #                                                                                     [('desk', False)] * 2 if subject == 'two_col_islands' else \
        #                                                                                     [('storage', False), ('desk', False)],
        #                                                                                     updated_boundary_against4remained_BOX)] 
        subjects_in_X_axis = [('low_cabinet', False)] * 2 if subject == 'low_cabinets' else \
                                [('desk', False)] * 2 if subject == 'two_col_islands' else \
                                [('low_cabinet', False), ('desk', False)]
        
        first_none_empty, last_none_empty = _get_non_empty_boundary(_partial_individual)

        if subject == first_none_empty and subject == last_none_empty:
            left_spacing, right_spacing = [__get_spacing_for_each_boundary(sub, 'longside', boundary, axis='Y', **exists)
                                            for (sub, _), boundary, exists in zip(subjects_in_X_axis, updated_boundary_against4remained_BOX, _main_passageways4boundary_against)]
        elif subject == first_none_empty:
            left_spacing, right_spacing = [__get_spacing_for_each_boundary(sub, 'longside', boundary, axis='Y', **exists) if i == 0 else __get_spacing_for_each_boundary(sub, 'longside', boundary, axis='Y')
                                            for i, ((sub, _), boundary, exists) in enumerate(zip(subjects_in_X_axis, updated_boundary_against4remained_BOX, _main_passageways4boundary_against))]
        elif subject == last_none_empty:
            left_spacing, right_spacing = [__get_spacing_for_each_boundary(sub, 'longside', boundary, axis='Y', **exists) if i == 1 else __get_spacing_for_each_boundary(sub, 'longside', boundary, axis='Y')
                                            for i, ((sub, _), boundary, exists) in enumerate(zip(subjects_in_X_axis, updated_boundary_against4remained_BOX, _main_passageways4boundary_against))]
        else:
            left_spacing, right_spacing = [__get_spacing_for_each_boundary(sub, 'longside', boundary, axis='Y')
                                            for (sub, _), boundary, exists in zip(subjects_in_X_axis, updated_boundary_against4remained_BOX, _main_passageways4boundary_against)]


        # if subject == 'two_col_islands' and user_desk_spacing is not None:
        #     left_spacing = user_desk_spacing

        desk_w4mixed=desk_width if subject.startswith('mixed') else None

        (x, y), (X, Y) = remained_BOX
        if subject == 'two_col_islands':
            _, w = sizes['desk']
            if user_desk:
                _, w = user_desk
        else:
            _, w = sizes['storage']

        self_spacing = user_desk_spacing if subject == 'two_col_islands' and user_desk_spacing is not None else None
        nrows = min(num_of_subjects, _calcu_nrows4subjects(subject, w, X - left_spacing - right_spacing,
                                                           self_spacing=self_spacing, desk_w4mixed=desk_w4mixed))
        if nrows > 0:
            length = _calcu_occupied_length_for_subjects(subject, nrows, w,
                                                         self_spacing=self_spacing, desk_w4mixed=desk_w4mixed)
            if subject == 'low_cabinets':
                _y, _Y = y4storage, length4storage
            else:
                _y, _Y = y4desks, length4desks
            if _Y >= desk_length:
                if user_desk_spacing and subject == 'two_col_islands' and has_mixed_cabinets_island > 0:
                    left_spacing = self_spacing
                RECTs[subject] = ((x + left_spacing, _y), (length, _Y))
                remained_BOX = ((x + left_spacing + length, y), (X - left_spacing - length, Y))
                updated_left_boundary = 'storage' if subject == 'low_cabinets' else 'desk'
                updated_boundary_against4remained_BOX[0] = (updated_left_boundary, False)
            else:
                nrows = 0
                RECTs[subject] = None
        else:
            RECTs[subject] = None

        if subject == first_none_empty and nrows == 0:
            _partial_individual = _update_partial_individual(subject, 0, _partial_individual)

        updated_plmts[subject] = nrows
    return RECTs, updated_plmts

def _bound_main_zone_in_X_axis(relative_main_door, relative_main_zone, comp_upbounds, partial_individual, 
                               num_of_storage_in_axises, num_of_printer_sets_in_axises, 
                               num_of_accompaniment_seats,
                               boundary_against_in_Y_axises, boundary_against=('window', 'wall'), 
                               inputs4global_layout=None,
                               inputs4local_layout=None, var_num_of_low_cabinets=None, var_num_of_small_lockers=None, 
                               latest_spacing=latest_spacing,
                               sizes=sizes, rotations_of_directions=rotations_of_directions):
    num_of_printer_sets_near_walls, relative_plmts4printer_sets_and_storage, updated_relative_main_zone, \
        _boundary_against_in_Y_axis4updated_main_zone, _boundary_against4updated_main_zone, \
            *overbounds_near_walls = _place_printer_sets_and_storage_near_walls(num_of_storage_in_axises, num_of_printer_sets_in_axises, comp_upbounds,
                                                                                boundary_against_in_Y_axises, boundary_against,
                                                                                relative_main_zone,
                                                                                relative_main_door=relative_main_door)
    # just for debugging: 
    #     - find out that this bug is due to the extension of main zones
    # if all(key == value for key, value in zip(relative_plmts4printer_sets_and_storage.keys(), ['down', 'left', 'up'])):
    #     pass

    _main_passageways4boundaries = [{'exists_main_passageway': exists,
                                    'user_main_passageway_width': inputs4global_layout['mainHallway'] if inputs4global_layout else None} 
                                    for *_, exists in boundary_against_in_Y_axises + boundary_against]
    down_boundary, up_boundary = _boundary_against_in_Y_axis4updated_main_zone
    if num_of_accompaniment_seats:
        up_subject, up_subject_side = 'accompany_seat', 'longside'
    else:
        up_subject, up_subject_side = 'desk', 'shortside'
    spacing4boundaries = [
        __get_spacing_for_each_boundary('low_cabinet', 'longside', down_boundary, **_main_passageways4boundaries[0]),
        __get_spacing_for_each_boundary(up_subject, up_subject_side, up_boundary, **_main_passageways4boundaries[1])
    ] 

    left_boundary, right_boundary = _boundary_against4updated_main_zone
    subject_on_left, subject_on_right = _get_subject_near_boundaries(partial_individual)
    spacing4boundaries += [
        __get_spacing_for_each_boundary(subject_on_left, 'longside', left_boundary, axis='Y', **_main_passageways4boundaries[2]),
        __get_spacing_for_each_boundary(subject_on_right, 'longside', right_boundary, axis='Y', **_main_passageways4boundaries[3])
    ]
    spacing4boundaries = dict(zip(['down', 'up', 'left', 'right'], spacing4boundaries))
    # spacing4boundaries['down'] = main_passageway_width

    # desk_shortside_against_main_passageway = spacing_in_4D['desk'][f'against_{down_neighbor}'][1][0] if down_neighbor in ['printer_set','storage'] else \
    #                                             spacing_in_4D['desk']['against_main_passageway'][1][0]

    
    RECTs_dict, num_of_low_cabinets, num_of_small_lockers = [None] * 3
    if inputs4local_layout:
        user_desk = (inputs4local_layout['width'], inputs4local_layout['height'])
        user_desk_spacing = inputs4local_layout['islandSpaceing'] if 'islandSpaceing' in inputs4local_layout.keys() else None
        # num_of_accompaniment_seats = inputs4local_layout['accompanyment_seats']

        (x, y), (X, Y) = updated_relative_main_zone
        if down_boundary[0] == 'islands':
            spacing4boundaries['down'] = 0
        _updated_relative_main_zone = ((x, y + spacing4boundaries['down']), (X, Y - spacing4boundaries['down'] - spacing4boundaries['up']))
        RECTs_dict, num_of_low_cabinets, num_of_small_lockers = _place_components_within_main_zone_for_local_layout(partial_individual, var_num_of_low_cabinets, var_num_of_small_lockers,
                                                                                                                    _updated_relative_main_zone, _boundary_against4updated_main_zone,
                                                                                                                    user_desk=user_desk, user_desk_spacing=user_desk_spacing)
        
        _partial_individual = partial_individual
        partial_individual = [0 if component not in RECTs_dict.keys() else  
                                len(RECTs_dict['storage_col_by_col']) if component == 'low_cabinets' else 
                                    len(RECTs_dict[component])
                              for component in ['two_col_islands', 'low_cabinets', 'mixed_island']]
        
        RECTs = [None] * 4
        if 'mixed_island' in RECTs_dict.keys() and RECTs_dict['mixed_island']:
            RECTs[1] = RECTs_dict['mixed_island'][-1]
        if 'two_col_islands' in RECTs_dict.keys():
            startX, endX = None, None
            maxY = None
            y = None
            for RECT in RECTs_dict['two_col_islands']:
                (x, y), (X, Y) = RECT
                if startX is None:
                    startX = x
                endX = x + X
                if maxY is None or maxY < Y:
                    maxY = Y
            RECTs[-2] = ((startX, y), (endX - startX, maxY))
    else:
        user_desk = (inputs4global_layout['tableWidth'], inputs4global_layout['tableHeight'])
        user_desk_spacing = inputs4global_layout['islandSpaceing']

        _main_passageways4boundary_against = _main_passageways4boundaries[2:]
        _RECTs, updated_plmts = _place_components_within_main_zone(partial_individual, updated_relative_main_zone, 
                                                                   _boundary_against4updated_main_zone, _main_passageways4boundary_against,
                                                                    spacing4boundaries['up'], spacing4boundaries['down'],
                                                                    user_desk=user_desk, user_desk_spacing=user_desk_spacing)
        _partial_individual = partial_individual
        RECTs = [_RECTs[component] for component in ['low_cabinets', 'mixed_island', 'two_col_islands']]
        partial_individual = [updated_plmts[component] for component in ['two_col_islands', 'low_cabinets', 'mixed_island']]
        RECTs += [None]
        # partial_individual += [False, 0]

    desk_length, desk_width = user_desk

    relative_origin, (X, Y) = updated_relative_main_zone
    length = Y - spacing4boundaries['up']
    length4desks = length - sizes['storage'][1] - spacing4boundaries['down']
    length4cabinets = length4desks + sizes['storage'][1]
    num_of_subjects_per_col = {subject: max(math.floor(its_length / (sizes['storage'][0] if subject != 'desk' else desk_length)), 0) 
                               for subject, its_length in zip(['desk', 'cabinet', 'mixed_cabinet'], [length4desks, length4cabinets, length4desks])}
    if inputs4local_layout:
        num_of_subjects_per_col['mixed_desk'] = num_of_subjects_per_col['desk']

    num_of_overbounds = 0
    if X < 0 or Y < 0:
        num_of_overbounds = 1

    # RECTs = [None] * 4
    num_of_two_col_islands, _, has_mixed_cabinets_island = partial_individual
    # # , *_ = partial_individual
    # # if num_of_two_col_islands == 0:
    # #     num_of_overbounds = 10**20
    # # else:
    # # spacing = __update_spacing(boundary_against, spacing=spacing)
    # RECTs = _get_RECTs(RECTs, num_of_subjects_per_col, partial_individual, 
    #                    spacing4boundaries['down'], spacing4boundaries['left'],
    #                    relative_origin=relative_origin)

    # # _, (right_neighbor, _) = _boundary_against4updated_main_zone
    # x, y = relative_origin
    # boundary_point = x + X
    _get_end_point = lambda RECT: sum(RECT[i][0] for i in range(2))

    # if RECTs[-2]:
    #     end_point =  _get_end_point(RECTs[-2])
    #     # end_point_slash = end_point + spacing['desk'][f'against_{right_neighbor}']['longside']
    # elif RECTs[1]:
    #     end_point = _get_end_point(RECTs[1])
    #     # end_point_slash = end_point + spacing['desk'][f'against_{right_neighbor}']['longside']
    # elif RECTs[0]:
    #     end_point = _get_end_point(RECTs[0])
    #     # end_point_slash = end_point + spacing['storage'][f'against_{right_neighbor}']['longside']
    # else:
    #     end_point = x
    # end_point_slash = end_point + spacing4boundaries['right']

    # if boundary_point < end_point_slash or any(value <= 0 and num > 0 for value, num in zip(num_of_subjects_per_col.values(), partial_individual)):
    #     num_of_overbounds = 1

    
    overbounds_of_high_cabinets_near_wall = 0
    # *_, subject_near_wall, num_of_subjects_near_wall = partial_individual
    # if not subject_near_wall and num_of_subjects_near_wall > comp_upbounds['high_cabinets'][0]:
    #     overbounds_of_high_cabinets_near_wall = 1


    bound_in_accompaniment_seats_without_islands = 0
    new_num_of_subjects_per_col = deepcopy(num_of_subjects_per_col)
    rectangles4accompaniment_seats = []
    if num_of_accompaniment_seats:
        rangeX4accompaniment_seats = [None, None]
        if inputs4local_layout:
            num_of_available_seats = num_of_two_col_islands

            if RECTs[-2]:
                (x, _), _ = RECTs[-2]
                rangeX4accompaniment_seats = (x, _get_end_point(RECTs[-2]))
        else:
            num_of_available_seats = has_mixed_cabinets_island + num_of_two_col_islands

            if RECTs[1]:
                (x, _), _ = RECTs[1]
                x = x + sizes['storage'][1] - desk_width
                rangeX4accompaniment_seats = [x, _get_end_point(RECTs[1])]
            if RECTs[-2]:
                if RECTs[1] is None:
                    (x, _), _ = RECTs[-2]
                    rangeX4accompaniment_seats[0] = x
                rangeX4accompaniment_seats[1] = _get_end_point(RECTs[-2])
        
        rectangles4accompaniment_seats = _place_accompany_seats(num_of_accompaniment_seats, num_of_available_seats, rangeX4accompaniment_seats, 
                                                                  spacing4boundaries['up'], updated_relative_main_zone,
                                                                  user_desk=user_desk, user_desk_spacing=user_desk_spacing)
        
        remained_length = length - sizes['chair'][1]- desk_width \
                                    - latest_spacing['desk']['against_accompany_seat'][__map_side_to_index('shortside')][__map_side_to_index('longside')] - \
                                        - sizes['storage'][1] - spacing4boundaries['down']
        new_num_of_subjects_per_col = _update_num_of_subjects_within_main_zone(num_of_subjects_per_col, rectangles4accompaniment_seats, 
                                                                                num_of_two_col_islands, RECTs, 
                                                                                remained_length, length4desks,
                                                                                inputs4local_layout=inputs4local_layout,
                                                                                user_desk=user_desk)
        _num_of_desks4available_seats = []
        if RECTs[1] and not inputs4local_layout:
            _num_of_desks4available_seats.append(new_num_of_subjects_per_col['mixed_desk'])
        if RECTs[-2]:
            _num_of_desks4available_seats += new_num_of_subjects_per_col['desk']
        bound_in_accompaniment_seats_without_islands = 1 if any(num == 0 for num in _num_of_desks4available_seats) else 0
    
    assigned_num_of_accompaniment_seats = len(rectangles4accompaniment_seats)
    insufficiency_of_accompaniment_seats = 1 if assigned_num_of_accompaniment_seats < num_of_accompaniment_seats else 0
    return RECTs_dict, num_of_low_cabinets, num_of_small_lockers, \
            partial_individual, num_of_printer_sets_near_walls, relative_plmts4printer_sets_and_storage, \
            rectangles4accompaniment_seats, \
            RECTs, new_num_of_subjects_per_col, \
            updated_relative_main_zone, _boundary_against4updated_main_zone, \
            *overbounds_near_walls, \
            assigned_num_of_accompaniment_seats, insufficiency_of_accompaniment_seats, bound_in_accompaniment_seats_without_islands,\
            num_of_overbounds, overbounds_of_high_cabinets_near_wall
            # overbounds_in_parallel2x4storage, overbounds_of_storage, overbounds_of_printer_sets, \


def bound_main_zone(main_door, original_main_zone, main_zone, desk_orientation, passageway_location, comp_upbounds, partial_individual, 
                    num_of_storage_in_axises, num_of_printer_sets_in_axises, 
                    num_of_accompaniment_seats, 
                    boundary_against_in_Y_axis, boundary_against=('window', 'wall'), 
                    inputs4global_layout=None,
                    inputs4local_layout=None, var_num_of_low_cabinets=None, var_num_of_small_lockers=None,
                    unfold=False):
    assert desk_orientation == 0

    (x, y), (X, Y) = main_zone
    relative_main_zone = ((0, 0), (X, Y))
    _get_relative_boundary_againsts = lambda boundary_againsts: [(wall, line if line is None else LineString([Point(b_x - x, b_y - y) for b_x, b_y in list(line.coords)]), exists_main_passageway) 
                                                                 for wall, line, exists_main_passageway in boundary_againsts]
    relative_boundary_against_in_Y_axis = _get_relative_boundary_againsts(boundary_against_in_Y_axis)
    relative_boundary_againsts = _get_relative_boundary_againsts(boundary_against)
    if main_door:
        relative_main_door = (main_door.x - x, main_door.y - y)
    else:
        relative_main_door = main_door
    # if desk_orientation:
    #     relative_main_zone = ((0, 0), (Y, X))

    (ox, oy), (oX, oY) = original_main_zone
    with_original_main_zone_extended_by = (x - ox, (x + X)- (ox + oX))

    _partial_individual = partial_individual

    num_of_low_cabinets, num_of_small_lockers = [None] * 2
    RECTs_dict, num_of_low_cabinets, num_of_small_lockers, \
    partial_individual, num_of_printer_sets_near_walls, relative_plmts4printer_sets_and_storage, relative_rectangles4accompaniment_seats, \
        relative_RECTs, new_num_of_subjects_per_col, \
            updated_relative_main_zone, _boundary_against4updated_main_zone, *results = _bound_main_zone_in_X_axis(relative_main_door, relative_main_zone, comp_upbounds, partial_individual, 
                                                                                        num_of_storage_in_axises, num_of_printer_sets_in_axises, 
                                                                                        num_of_accompaniment_seats,
                                                                                        relative_boundary_against_in_Y_axis, relative_boundary_againsts,
                                                                                        inputs4global_layout=inputs4global_layout,
                                                                                        inputs4local_layout=inputs4local_layout, var_num_of_low_cabinets=var_num_of_low_cabinets, var_num_of_small_lockers=var_num_of_small_lockers)
    # _extend_wall = 'against_down_wall'
    # if _extend_wall in relative_rectangles4printer_sets_dict.keys():
    #     _by, _ = with_original_main_zone_extended_by
    #     relative_rectangles4printer_sets_dict[_extend_wall] = [(((x - _by, y), rect), rotation) for ((x, y), rect), rotation in relative_rectangles4printer_sets_dict[_extend_wall]]
    updated_main_zone = transform_RECTs([updated_relative_main_zone], desk_orientation, passageway_location, main_zone)[0]
    RECTs = transform_RECTs(relative_RECTs, desk_orientation, passageway_location, main_zone)
    if inputs4local_layout:
        relative_rectangles = defaultdict(list)
        rectangles = {}
    else:
        relative_rectangles = unfold_RECTs_in_main_zone(new_num_of_subjects_per_col, relative_RECTs, partial_individual,
                                                        inputs4global_layout=inputs4global_layout)
        # relative_rectangles['printer_sets'] = list(chain.from_iterable(relative_rectangles4printer_sets_dict.values()))
        rectangles = {comp: transform_components(rects, desk_orientation, passageway_location, main_zone) for comp, rects in relative_rectangles.items()}

    components = None
    if unfold:
        # relative_plmts_in_partitions, relative_RECTs_in_partitions, boundary_against4partitioned_zones = plmts4storage_in_X_axis
        # rectangles4storage_in_X_axis = unfold_RECTs_in_partitions(relative_RECTs_in_partitions, relative_plmts_in_partitions, boundary_against4partitioned_zones, )
        # relative_components4storage_in_X_axis = unfold_components_in_sub_zone(rectangles4storage_in_X_axis, var_num_of_storage_in_X_axis4main_zone)
        
        relative_components4storage = {}
        for (wall, shifted_zone4both, *_), plmts_partitioned_by_door in relative_plmts4printer_sets_and_storage.items():
            if wall in ['left', 'right']:
                storage_orientation = True
            else:
                storage_orientation = False
            wall_location = wall
            sub_zone = shifted_zone4both
            # sub_zone = transform_RECTs([shifted_zone4both], desk_orientation, passageway_location, main_zone)[0]

            for (splitted_zone_by_door, rectangles4printer_sets, partitioned_zones_by_printer_sets, boundary_against4partitioned_zones,
                                        summed_plmts, plmts_in_partitions, RECTs_in_partitions) in plmts_partitioned_by_door:
                rectangles4printer_sets = transform_components(rectangles4printer_sets, storage_orientation, wall_location, sub_zone)
                # partitioned_zones4storage = transform_RECTs(partitioned_zones, storage_orientation, wall, sub_zone)


                # storage_RECTs_in_partitions = [transform_RECTs(relative_RECTs_in_partition, storage_orientation, wall_location, sub_zone) 
                #                                for relative_RECTs_in_partition in relative_plmt_results4storage[1]]
                rectangles4storage_in_X_axis = unfold_RECTs_in_partitions(RECTs_in_partitions, plmts_in_partitions, boundary_against4partitioned_zones)
                _summed_plmts = list(chain.from_iterable([summed_plmts[subject] for subject in ['big_lockers', 'high_cabinets']]))
                components4storage_in_X_axis = unfold_components_in_sub_zone(rectangles4storage_in_X_axis, _summed_plmts)
                components4storage = {comp: transform_components(rects, storage_orientation, wall_location, sub_zone) for comp, rects in components4storage_in_X_axis.items()}

                # storage_plmts_in_partitions = [{subject: (not parallel2x if storage_orientation else parallel2x, nrows, ncols) for subject, (parallel2x, nrows, ncols) in relative_plmts_in_partition.items()} 
                #                                 for relative_plmts_in_partition in relative_plmt_results4storage[0]]

                relative_rectangles['printer_sets'] += rectangles4printer_sets
                # relative_components4storage = {**relative_components4storage, **components4storage}
                relative_components4storage = __combine_multiple_defaultdictlists(relative_components4storage, components4storage)

        if inputs4local_layout:
            relative_components4local_layout = unfold_components_in_main_zone_for_local_layout(RECTs_dict, new_num_of_subjects_per_col, inputs4local_layout)
            relative_components4local_layout['accompaniment_seat_in_unit1'] = [(rect, 180) for rect in relative_rectangles4accompaniment_seats]
            if 'printer_sets' in relative_rectangles.keys():
                printers, paper_shredders = __unfold_a_partitioned_row_of_printer_sets(relative_rectangles['printer_sets'])
                relative_components4local_layout['printer'] = printers
                relative_components4local_layout['paper_shredder'] = paper_shredders
            relative_components = __combine_multiple_defaultdictlists(relative_components4local_layout, relative_components4storage)
        else:
            relative_rectangles['accompaniment_seats'] = [(rect, 180) for rect in relative_rectangles4accompaniment_seats] 
            relative_components = unfold_components_in_main_zone(relative_rectangles, inputs4global_layout=inputs4global_layout)
            # relative_components = {**relative_components, **relative_components4storage}
            relative_components = __combine_multiple_defaultdictlists(relative_components, relative_components4storage)
        components = {comp: transform_components(rects, desk_orientation, passageway_location, main_zone) for comp, rects in relative_components.items()}
    return num_of_low_cabinets, num_of_small_lockers, \
            components, rectangles, RECTs, \
            partial_individual, num_of_printer_sets_near_walls, relative_plmts4printer_sets_and_storage, new_num_of_subjects_per_col, \
                updated_main_zone, _boundary_against4updated_main_zone, *results