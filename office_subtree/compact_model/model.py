import random
from copy import deepcopy
from itertools import chain
from scipy.spatial.distance import jensenshannon
import math
from collections import defaultdict
import numpy as np

from .bound_in_general import bound_in_general
from .bound_storage import bound_storage
from .connect_main_zones import connect_main_zones, connect_main_zones_in_general
from .bound_main_zone import __get_walls4main_zone

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from general.utils import calcu_max_matrix_within_zone4subjects, calcu_max_cols4printer_sets_alongside_wall
from general.configs import spacing, spacing_in_4D, sizes


def __reflect(rect, boundary):
    (x, y), (X, Y) = rect
    (_x, _y), (_X, _Y) = boundary
    return ((_x + _X - x + _x - X, y), (X, Y))


def _reflect_back_dict(_zone_list, boundary):
    _boundary = ((0, 0), boundary)
    res = [{comp: [(__reflect(rect, _boundary), (rotation + 180) % 360) for rect, rotation in rects] for comp, rects in zone.items()} for zone in _zone_list]
    return res

def _reflect(main_zones, desk_orientations4main_zones, boundary_against4main_zones, boundary):
    _boundary = ((0, 0), boundary)
    reflected_results = [
        [__reflect(zone, _boundary) for zone in main_zones[::-1]],
        desk_orientations4main_zones[::-1],
        [neighbors[::-1] for neighbors in boundary_against4main_zones[::-1]]
    ]
    return reflected_results


def calcu_bounds_for_individual(main_zones, desk_orientations4main_zones, sub_zones, 
                                boundary_against_in_Y_axis4main_zones, boundary_against4main_zones,
                                inputs4global_layout=None,
                                inputs4local_layout=None,
                                sizes=sizes, spacing_in_4D=spacing_in_4D):
    def _calcu_component_upbounds(main_zones, sub_zones):
        upbounds4main_zones, upbounds4subzones = [], []
        
        for (_, rect), desk_orientation in zip(main_zones, desk_orientations4main_zones):
            components = ['two_col_islands', 'low_cabinets', 'mixed_island']
                        #   , 'big_lockers', 'high_cabinets']     
            _upbounds = {comp: calcu_max_matrix_within_zone4subjects(comp, desk_orientation, rect) for comp in components}
            X, Y = rect
            l, _ = sizes['printer_set']
            # _upbounds['printer_sets'] = (int(Y/l), int(X/l), int(Y/l))
            _upbounds['printer_sets'] = [calcu_max_cols4printer_sets_alongside_wall(length) for length in [Y, X, Y]]

            _, w = sizes['storage']
            maxY = min(w * 6 + spacing_in_4D['storage']['against_storage'][0][0], Y)
            _upbounds4printer_sets_and_storage_in_axises = {}
            for axis in ['X', 'Y']:
                _rect4storage_in_axis = (X, maxY) if axis == 'X' else (Y, maxY)
                key = f'in_{axis}_axis'
                _upbounds4printer_sets_and_storage_in_axises[key] = {comp: [calcu_max_matrix_within_zone4subjects(comp, parallel2x, _rect4storage_in_axis) 
                                                                            for parallel2x in [False, True]]
                                                                    for comp in ['big_lockers', 'high_cabinets']}
                _upbounds4printer_sets_and_storage_in_axises[key]['printer_sets'] = int(_rect4storage_in_axis[0] / sizes['printer_set'][0])
            _upbounds = {**_upbounds, **_upbounds4printer_sets_and_storage_in_axises }
            upbounds4main_zones.append(_upbounds)

        for _, rect in sub_zones:
            components = ['big_lockers', 'high_cabinets', 'printer_sets']
            _upbounds = {comp: [calcu_max_matrix_within_zone4subjects(comp, parallel2x, rect) for parallel2x in [False, True]] for comp in components}
            upbounds4subzones.append(_upbounds)
        return upbounds4main_zones, upbounds4subzones


    upbounds4main_zones, upbounds4subzones = _calcu_component_upbounds(main_zones, sub_zones)

    walls4main_zones = []
    for boundary_against_in_Y_axis4main_zone, boundary_against4main_zone in zip(boundary_against_in_Y_axis4main_zones, boundary_against4main_zones):
        boundary_againsts = boundary_against_in_Y_axis4main_zone + boundary_against4main_zone
        corresponding_axises = ['X'] * 2 + ['Y'] * 2
        available_walls4main_zone = [(boundary_against, axis) for (boundary_against, *_), axis in zip(boundary_againsts, corresponding_axises) if boundary_against == 'wall']
        walls4main_zones.append(available_walls4main_zone)

    ups = []
    ups4printer_sets_in_main_zones, ups4storage_in_main_zones = [], []
    ups4islands_in_main_zones = []
    for _upbounds, walls4main_zone in zip(upbounds4main_zones, walls4main_zones):
        comp_list = ['two_col_islands', 'low_cabinets', 'mixed_island'], ['big_lockers', 'high_cabinets']
        ups += [_upbounds[comp][0] for comp in comp_list[0]]
        # ups += [1, max(_upbounds[comp][0] for comp in comp_list[1])]
        up4islands_in_main_zone = sum(_upbounds[comp][0] for comp in ['two_col_islands', 'mixed_island'])
        ups4islands_in_main_zones.append(up4islands_in_main_zone)

        for boundary_against, axis in walls4main_zone:
            __upbounds = _upbounds[f'in_{axis}_axis']
            ups4printer_sets_in_main_zones += [__upbounds['printer_sets']]
            for comp in ['big_lockers', 'high_cabinets']:
                parallel2x_results = __upbounds[comp]
                max_ncols = max(ncols for _, ncols in parallel2x_results)
                max_nrows = max(nrows for nrows, _ in parallel2x_results)
                ups4storage_in_main_zones += [1, max_nrows, max_ncols]
    

    ups4printer_sets_in_sub_zones = []
    for _upbounds in upbounds4subzones:
        for comp, parallel2x_results in _upbounds.items():
            max_ncols = max(ncols for _, ncols in parallel2x_results)
            if comp == 'printer_sets':
                ups4printer_sets_in_sub_zones += [1, max_ncols]
            else:
                max_nrows = max(nrows for nrows, _ in parallel2x_results)
                ups += [1, max_nrows, max_ncols]

    ups += ups4printer_sets_in_sub_zones

    ups += ups4storage_in_main_zones
    ups += ups4printer_sets_in_main_zones

    _num_of_accompaniment_seats = inputs4global_layout['stepNumber'] if inputs4global_layout else inputs4local_layout['accompanyment_seats']
    ups += [_num_of_accompaniment_seats] * len(main_zones)
    if inputs4local_layout:
        ups += [inputs4local_layout['low_cabinets']] * len(main_zones)
        ups += [inputs4local_layout['small_lockers']] * len(main_zones)
        # ups += list(chain.from_iterable([1] * up  for up in ups4islands_in_main_zones))

    # ups += [1]
    lows = [0] * len(ups)
    return walls4main_zones, (upbounds4main_zones, upbounds4subzones), lows, ups


def _generate_an_individual(icls, lows, ups):   
    ind = [random.randint(l, u) for l, u in zip(lows, ups)]
    return icls(ind)


def find_nearest_printer_set(RECT4island, printer_sets):
    _get_center_coord = lambda x, y, X, Y: (x + X/2, y + Y/2)
    _get_distance = lambda coord1, coord2: sum(abs(coord1[i] - coord2[i]) for i in range(2))

    island_center = _get_center_coord(*RECT4island[0], *RECT4island[1])

    index, distance = None, None
    for i, ((origin, rect), _ )in enumerate(printer_sets):
        center = _get_center_coord(*origin, *rect)
        dist = _get_distance(island_center, center)
        if index is None or distance < dist:
            index, distance = i, dist
    return (index, distance)

def group_islands_by_printer_sets(islands, islands2printer_sets):
    printer_sets2islands = defaultdict(list)

    for i, (pi, distance) in islands2printer_sets.items():
        printer_sets2islands[pi].append(islands[i])
    return printer_sets2islands

def bound(main_door, boundary, upbounds, main_zones, desk_orientations4main_zones, passageway_locations4main_zones, 
          walls4main_zones, boundary_against_in_Y_axis4main_zones, boundary_against4main_zones, connect_func,
          sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, individual, 
          unfold=False,
          inputs4global_layout=None,
          inputs4local_layout=None):
    # with_main_zones_reflected, individual = individual[-1], individual[:-1]
    with_main_zones_reflected = False

    if inputs4local_layout:
        # upbounds4main_zones, _ = upbounds
        # max_num_of_islands4main_zones = [sum(upbound[comp][0] for comp in ['two_col_islands', 'mixed_island']) for upbound in upbounds4main_zones]
        # _var_num_of_storage_on_shortside_of_islands4main_zones, individual = individual[-len(main_zones)*sum(max_num_of_islands4main_zones):], individual[:-len(main_zones)*sum(max_num_of_islands4main_zones)]
        # var_num_of_storage_on_shortside_of_islands4main_zones = [_var_num_of_storage_on_shortside_of_islands4main_zones[sum(max_num_of_islands4main_zones[:i]):sum(max_num_of_islands4main_zones[:i]) + max_num_of_islands4main_zone]
        #                                                          for i, max_num_of_islands4main_zone in enumerate(max_num_of_islands4main_zones)]

        var_num_of_small_lockers4main_zones, individual = individual[-len(main_zones):], individual[:-len(main_zones)]
        var_num_of_low_cabinets4main_zones, individual = individual[-len(main_zones):], individual[:-len(main_zones)]
    else:
        var_num_of_small_lockers4main_zones, var_num_of_low_cabinets4main_zones = None, None

    var_num_of_accompaniment_seats4main_zones, individual = individual[-len(main_zones):], individual[:-len(main_zones)]


    num_of_walls4main_zones = [len(walls) for walls in walls4main_zones]
    partial_individual4printer_sets4main_zones, individual = individual[-sum(num_of_walls4main_zones):], individual[:-sum(num_of_walls4main_zones)]
    delta = 6
    partial_individual4storage4main_zones, individual = individual[-sum(num_of_walls4main_zones)*delta:], individual[:-sum(num_of_walls4main_zones)*delta]

    def _split_by_walls(partial_individual, num_of_walls4main_zones, delta=1):
        var_num_of_compoents_in_axises4main_zones = []
        i = 0 
        for num_of_walls in num_of_walls4main_zones:
            var_num_of_compoents_in_axises4main_zones.append(partial_individual[i:i+num_of_walls*delta])
            i += num_of_walls * delta
        return var_num_of_compoents_in_axises4main_zones
    
    var_num_of_printer_sets_in_axises4main_zones = _split_by_walls(partial_individual4printer_sets4main_zones, num_of_walls4main_zones)
    var_num_of_storage_in_axises4main_zones = _split_by_walls(partial_individual4storage4main_zones, num_of_walls4main_zones, delta=6)

    # var_num_of_printer_sets_in_axises4main_zones, individual = individual[-len(main_zones)*3:], individual[:-len(main_zones)*3]
    # var_num_of_printer_sets_in_axises4main_zones = [var_num_of_printer_sets_in_axises4main_zones[3*j:3*j + 3] for j in range(len(main_zones))]
    # nsteps = 6 * 3
    # var_num_of_storage_in_axises4main_zones, individual = individual[-len(main_zones)*nsteps:], individual[:-len(main_zones)*nsteps]
    # var_num_of_storage_in_axises4main_zones = [var_num_of_storage_in_axises4main_zones[nsteps*j:nsteps*j+nsteps] for j in range(len(main_zones))]

    if sub_zones:
        var_printer_sets4sub_zones, individual = individual[-len(sub_zones)*2:], individual[:-len(sub_zones)*2]
        var_printer_sets4sub_zones = [var_printer_sets4sub_zones[2*j:2*j+2] for j in range(len(sub_zones))]
    else:
        var_printer_sets4sub_zones = [(0, 0)] * len(sub_zones)


    _main_zones, _desk_orientations4main_zones, _boundary_against4main_zones = (main_zones, desk_orientations4main_zones, boundary_against4main_zones)
    # if with_main_zones_reflected:
    #     _main_zones, _desk_orientations4main_zones, _boundary_against4main_zones = _reflect(main_zones, desk_orientations4main_zones, boundary_against4main_zones, boundary)                                                                            
    #     var_num_of_printer_sets4main_zones = var_num_of_printer_sets4main_zones[::-1]
        
    total_num_of_low_cabinets, total_num_of_small_lockers, \
    components_dict, rectangles_dict, RECTs_dict, \
    num_of_printer_sets_near_walls4sub_zones, num_of_printer_sets_near_walls4main_zones, relative_plmts4printer_sets_and_storage4main_zones, \
    _boundary_against4updated_main_zones, \
    total_overbounds_of_parallel2x4storage, total_overbounds_of_storage, total_overbounds_of_printer_sets, \
    assigned_num_of_accompaniment_seats_list, total_insufficiency_of_accompaniment_seats, total_bound_in_accompaniment_seats_without_islands, \
    overbounds_within_main_zones, overbounds_within_sub_zones, total_overbounds_of_high_cabinets_near_wall, \
    num_of_persons, num_of_subjects_per_col4main_zones, num_of_islands4storage_list, indexes = bound_in_general(main_door, boundary, _main_zones, _desk_orientations4main_zones, passageway_locations4main_zones, upbounds,
                                                                                                                boundary_against_in_Y_axis4main_zones, _boundary_against4main_zones, 
                                                                                                                 sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, 
                                                                                                                 var_num_of_storage_in_axises4main_zones, var_num_of_printer_sets_in_axises4main_zones, 
                                                                                                                 var_printer_sets4sub_zones, 
                                                                                                                 var_num_of_accompaniment_seats4main_zones, individual,
                                                                                                                 unfold=unfold,
                                                                                                                 inputs4global_layout=inputs4global_layout,
                                                                                                                 inputs4local_layout=inputs4local_layout, 
                                                                                                                 var_num_of_low_cabinets4main_zones=var_num_of_low_cabinets4main_zones, var_num_of_small_lockers4main_zones=var_num_of_small_lockers4main_zones)
    if not inputs4local_layout:
        num_of_persons += sum(assigned_num_of_accompaniment_seats_list)

    total_num_of_islands4storage = sum(num_of_islands4storage_list)
    gaps_of_plmts4walls_in_main_zones, storage_partition_below_two_col_islands, penalties_in_order_of_priority, storage_assigned_sofar, required_storage, \
    _priorities, storage_plmts, incremental_storages = bound_storage(_main_zones, _desk_orientations4main_zones, boundary_against_in_Y_axis4main_zones, _boundary_against4main_zones,
                                                        var_num_of_storage_in_axises4main_zones, var_num_of_printer_sets_in_axises4main_zones, relative_plmts4printer_sets_and_storage4main_zones,
                                                        sub_zones, storage_orientations4sub_zones, 
                                                        RECTs_dict['sub_zones'], indexes, upbounds,
                                                        num_of_persons, num_of_subjects_per_col4main_zones, total_num_of_islands4storage, 
                                                        var_printer_sets4sub_zones, individual,
                                                        unfold=unfold,
                                                        inputs4global_layout=inputs4global_layout,
                                                        inputs4local_layout=inputs4local_layout)
    
    index4main_zones, _ = indexes
    penalty4island_connectivity = connect_func(RECTs_dict['main_zones'], _boundary_against4main_zones, _boundary_against4updated_main_zones) if connect_func else \
                                    connect_main_zones(index4main_zones, len(main_zones), individual)
    
    
    if with_main_zones_reflected:
        var_num_of_printer_sets4main_zones = var_num_of_printer_sets4main_zones[::-1]
        rectangles_dict['main_zones'] = _reflect_back_dict(rectangles_dict['main_zones'], boundary)
    

    # # islands = list(chain.from_iterable([rectangles for subject, rectangles in aggregated_rectangles_dict.items() ]))
    # islands = [[(rectangle, num_of_subjects_per_col['desk'] * (1 if subject == 'mixed_desk' else 2)) for rectangle in rectangles]
    #             for RECT_dict, num_of_subjects_per_col in zip(rectangles_dict['main_zones'], num_of_subjects_per_col4main_zones)
    #                 for subject, rectangles in RECT_dict.items() 
    #                     if subject in ['mixed_desk', 'two_col_islands']]
    # islands = list(chain.from_iterable(islands))
    # printer_sets = aggregated_rectangles_dict['printer_sets']
    # _islands2printer_sets = {i: find_nearest_printer_set(RECT4island, printer_sets) for i, ((RECT4island, _), _) in enumerate(islands)}
    # _grouped_islands = group_islands_by_printer_sets(islands, _islands2printer_sets)

    # desks = [[(rectangle, (1 if subject.startswith('mixed_') else 2) * int(subject.split('_in_unit')[-1])) for rectangle in rectangles]
    #          for RECTs_dict in components_dict['main_zones']
    #             for subject, rectangles in RECTs_dict.items() 
    #                 if 'desk' in subject]
    # desks = list(chain.from_iterable(desks))
    # _islands2printer_sets = {i: find_nearest_printer_set(RECT4island, printer_sets) for i, ((RECT4island, _), _) in enumerate(desks)}
    # _grouped_islands = group_islands_by_printer_sets(desks, _islands2printer_sets)
    
    return total_num_of_low_cabinets, total_num_of_small_lockers,\
            with_main_zones_reflected, penalty4island_connectivity,\
            (storage_partition_below_two_col_islands, components_dict, rectangles_dict, RECTs_dict,
            # (aggregated_components_dict, aggregated_rectangles_dict, RECTs_dict,
            # desks, printer_sets, _islands2printer_sets, _grouped_islands,
            gaps_of_plmts4walls_in_main_zones, num_of_printer_sets_near_walls4sub_zones, num_of_printer_sets_near_walls4main_zones,
            # var_num_of_printer_sets_in_axises4main_zones, 
            total_overbounds_of_parallel2x4storage, total_overbounds_of_storage, total_overbounds_of_printer_sets,
            assigned_num_of_accompaniment_seats_list, total_insufficiency_of_accompaniment_seats, total_bound_in_accompaniment_seats_without_islands,
            num_of_islands4storage_list, overbounds_within_main_zones, overbounds_within_sub_zones, total_overbounds_of_high_cabinets_near_wall, num_of_persons, 
            indexes), (penalties_in_order_of_priority, storage_assigned_sofar, required_storage, _priorities, storage_plmts, incremental_storages)



def bound_distribution_with_jensenshannon_func(target_distribution, goal_distribution):
    if sum(target_distribution) and sum(goal_distribution):
        target_prob_distribution = [num/sum(target_distribution) for num in target_distribution]
        goal_prob_distribution = [num/sum(goal_distribution) for num in goal_distribution]
        bound_in_approaching_goal_prob_distribution = jensenshannon(target_prob_distribution, goal_prob_distribution)
    else:
        bound_in_approaching_goal_prob_distribution = 1
    return bound_in_approaching_goal_prob_distribution

def _evaluate(main_door, boundary, upbounds, main_zones, desk_orientations4main_zones, passageway_locations4main_zones, 
              walls4main_zones, boundary_against_in_Y_axis4main_zones, boundary_against4main_zones, connect_func,
              sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, individual,
              unfold=False,
              inputs4global_layout=None):

    _, _, \
    with_main_zones_reflected, penalty4island_connectivity, \
    (storage_partition_below_two_col_islands, components_dict, rectangles_dict, RECTs_dict,
    # (aggregated_components_dict, aggregated_rectangles_dict, RECTs_dict,
    # islands, printer_sets, _islands2printer_sets, _grouped_islands,
    gaps_of_plmts4walls_in_main_zones, num_of_printer_sets_near_walls4sub_zones, num_of_printer_sets_near_walls4main_zones, 
    total_overbounds_of_parallel2x4storage, total_overbounds_of_storage, total_overbounds_of_printer_sets,
    assigned_num_of_accompaniment_seats_list, total_insufficiency_of_accompaniment_seats, total_bound_in_accompaniment_seats_without_islands,
    num_of_islands4storage_list, overbounds_within_main_zones, overbounds_within_sub_zones, total_overbounds_of_high_cabinets_near_wall, num_of_persons, 
    indexes), (penalties_in_order_of_priority, storage_assigned_sofar, required_storage, _priorities, storage_plmts, incremental_storages) = \
    bound(main_door, boundary, upbounds, main_zones, desk_orientations4main_zones, passageway_locations4main_zones, 
          walls4main_zones, boundary_against_in_Y_axis4main_zones, boundary_against4main_zones, connect_func,
              sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, individual,
              unfold=unfold,
              inputs4global_layout=inputs4global_layout)

    storage_opts = ['locker', 'cabinet']
    unsatisfiability_of_storage_requirements = 0
    for subject in storage_opts:
        if storage_assigned_sofar[subject] < required_storage[subject]:
            unsatisfiability_of_storage_requirements += 1

    required_num_of_printer_sets = math.ceil(num_of_persons / 50)
    num_of_printer_sets = sum(chain.from_iterable(num_of_printer_sets_near_walls4main_zone.values() for num_of_printer_sets_near_walls4main_zone in num_of_printer_sets_near_walls4main_zones)) + sum(num for _, num in num_of_printer_sets_near_walls4sub_zones)
    unsatisfiability_of_printer_sets = 1 if num_of_printer_sets < required_num_of_printer_sets else (num_of_printer_sets - required_num_of_printer_sets)**2

    # desk_distances = [(10**20 if _islands2printer_sets[i][-1] is None else _islands2printer_sets[i][-1]) * num_of_persons_per_island 
    #                     for i, (_, num_of_persons_per_island) in enumerate(islands)]
    # printer_set_usage = [sum(num_of_persons_per_island for _, num_of_persons_per_island in _grouped_islands[i]) if i in _grouped_islands.keys() else 0 
    #                         for i, _ in enumerate(printer_sets)]
   
    upbounds4main_zones, upbounds4sub_zones = upbounds
    allowed_distribution4printer_sets = defaultdict(list)
    # for upbound, (left_neighbor, right_neighbor), (down_neighbor, _) in zip(upbounds4main_zones, boundary_against4main_zones, boundary_against_in_Y_axis4main_zones):
    #     allowed_max_nums = [max_num if neighbor == 'wall' else 0 for max_num, neighbor in zip(upbound['printer_sets'], [left_neighbor, down_neighbor, right_neighbor])]
    #     allowed_distribution4printer_sets['main_zones'].append(allowed_max_nums)
    walls4main_zones = [__get_walls4main_zone(boundary_against_in_Y_axis4main_zone, boundary_against4main_zone) for boundary_against_in_Y_axis4main_zone, boundary_against4main_zone in zip(boundary_against_in_Y_axis4main_zones, boundary_against4main_zones)]
    max_num_of_printer_sets4main_zones = [{wall: calcu_max_cols4printer_sets_alongside_wall(wall_line.length) for *_, wall, wall_line, _ in walls4main_zone} for walls4main_zone in walls4main_zones]
    _sort_num_of_printer_sets4main_zones = lambda num_of_printer_sets4main_zones, priorities4walls={'down': 0, 'left': 1, 'right': 2, 'up': 3}: \
                                                    [[num for _ , num in sorted(num_of_printer_sets4main_zone.items(), key=lambda item: priorities4walls[item[0]])]
                                                        for num_of_printer_sets4main_zone in num_of_printer_sets4main_zones]
    # allowed_distribution4printer_sets['main_zones'] = [[upbounds4main_zone[f'in_{axis}_axis']['printer_sets'] for _, axis in walls4main_zone] for walls4main_zone, upbounds4main_zone in zip(walls4main_zones, upbounds4main_zones)]
    allowed_distribution4printer_sets['main_zones'] = _sort_num_of_printer_sets4main_zones(max_num_of_printer_sets4main_zones)
    allowed_distribution4printer_sets['sub_zones'] = [max(num for _, num in upbounds['printer_sets']) for upbounds in upbounds4sub_zones]
    _allowed_distribution4printer_sets = list(chain.from_iterable(allowed_distribution4printer_sets['main_zones'])) + allowed_distribution4printer_sets['sub_zones']

    distribution_of_printer_sets = list(chain.from_iterable(_sort_num_of_printer_sets4main_zones(num_of_printer_sets_near_walls4main_zones))) + [num for _, num in num_of_printer_sets_near_walls4sub_zones]
    bound_in_distribution_of_printer_sets = bound_distribution_with_jensenshannon_func(distribution_of_printer_sets, _allowed_distribution4printer_sets)


    _num_of_accompaniment_seats = inputs4global_layout['stepNumber']
    unsatisfiability_of_accompaniment_seats = 1 if sum(assigned_num_of_accompaniment_seats_list) < _num_of_accompaniment_seats else (_num_of_accompaniment_seats - sum(assigned_num_of_accompaniment_seats_list))**2
    bound_in_distribution_of_accompaniment_seats = bound_distribution_with_jensenshannon_func(assigned_num_of_accompaniment_seats_list, num_of_islands4storage_list)


    params = [
        unsatisfiability_of_accompaniment_seats, 
        unsatisfiability_of_storage_requirements, \
        *penalty4island_connectivity, \
        unsatisfiability_of_printer_sets, 
        total_overbounds_of_parallel2x4storage, total_overbounds_of_storage, total_overbounds_of_printer_sets, 
        total_insufficiency_of_accompaniment_seats, total_bound_in_accompaniment_seats_without_islands, 
        overbounds_within_main_zones, total_overbounds_of_high_cabinets_near_wall, \
        overbounds_within_sub_zones
    ]

    params = [10**50 * penalty for penalty in params]
    params += [
        -num_of_persons
    ]

    for prior in _priorities:
        if prior in ['sub_zones', 'main_zones_walls_in_axises']:
            for subject in storage_opts:
                params += list(chain.from_iterable(penalties_in_order_of_priority[prior][subject]))
        # elif prior == 'main_zones_walls':
        #     params += list(chain.from_iterable(penalties_in_order_of_priority[prior]))
        else:
            params += penalties_in_order_of_priority[prior]

    params += [     
        bound_in_distribution_of_printer_sets,  
        bound_in_distribution_of_accompaniment_seats
        # sum([sum(gaps_of_plmts4walls_in_main_zone.values()) for gaps_of_plmts4walls_in_main_zone in gaps_of_plmts4walls_in_main_zones]),
        # (storage_assigned_sofar['locker'] - required_storage['locker'])**2, 
        # (storage_assigned_sofar['cabinet'] - required_storage['cabinet'])**2
    ]
    return params