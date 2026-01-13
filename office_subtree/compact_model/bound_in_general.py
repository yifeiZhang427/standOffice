from collections import defaultdict
from copy import deepcopy

from .bound_main_zone import bound_main_zone
from .bound_sub_model import bound_sub_zone

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from general.configs import spacing


def _get_subject_near_boundary(partial_individual, left2right=True):
    subjects=['storage', 'storage' if left2right else 'desk', 'desk']
            #   , 'storage']

    # _partial_individual = partial_individual[:-2]
    _partial_individual = deepcopy(partial_individual)
    _partial_individual = _partial_individual[1:] + [_partial_individual[0]]
    _partial_individual += partial_individual[-1:]
    
    res, index = None, None
    _range = range(len(subjects)) 
    if not left2right:
        _range = reversed(_range)
    for j in _range:
        if _partial_individual[j] > 0:
            index = j
            res = subjects[index]
            break
    return (res, index)


_get_rangeY = lambda origin, rect: (origin[1], origin[1] + rect[1])
_within_rangeY = lambda curr_rangeY, refered_rangeY: refered_rangeY[0] <= curr_rangeY[0] and refered_rangeY[1] >= curr_rangeY[1]

def _extend_left_boundary(main_zone, partial_individual, boundary_against,
                          prev_main_zone, prev_partial_individual, prev_RECTs, prev_boundary_against):
    new_origin, (X, Y) = main_zone
    x, y = new_origin

    if _within_rangeY(_get_rangeY(*main_zone), _get_rangeY(*prev_main_zone)):

        left_neighbor, left_index = _get_subject_near_boundary(prev_partial_individual, left2right=False)
        if left_neighbor is None:
            (px, py), (pX, pY) = prev_main_zone
            new_origin = (px, y)
            # boundary_against[0] = prev_boundary_against[0]
            _, right_neighbor = boundary_against
            boundary_against = (prev_boundary_against[0], right_neighbor)
        else:
            (px, py), (pX, pY) = prev_RECTs[left_index]
            curr_subject, curr_index = _get_subject_near_boundary(partial_individual, left2right=True)
            _spacing = 0 if curr_subject is None else spacing[left_neighbor][f'against_{curr_subject}']['longside']
            endX = px + pX + _spacing
            if endX < x:
                new_origin = (endX, y)
            
    new_RECT = (X + (x - new_origin[0]), Y)
    new_main_zone = (new_origin, new_RECT)
    return boundary_against, new_main_zone

def _extend_right_boundary(main_zone, partial_individual, boundary_against,
                           next_main_zone, next_partial_individual, next_boundary_against):
    new_main_zone = main_zone
    
    if _within_rangeY(_get_rangeY(*main_zone), _get_rangeY(*next_main_zone)):
        origin, (X, Y) = main_zone
        x, y = origin

        (nx, ny), (nX, nY) = next_main_zone
        right_neighbor, right_index = _get_subject_near_boundary(next_partial_individual, left2right=True)
        if right_index is None:
            new_main_zone = (origin, (nx + nX - x, Y))
            # boundary_against[1] = next_boundary_against[1]
            left_neighbor, _ = boundary_against
            boundary_against = (left_neighbor, next_boundary_against[1])
        else:
            curr_subject, curr_index = _get_subject_near_boundary(partial_individual, left2right=False)
            _spacing = 0 if curr_subject is None else spacing[curr_subject][f'against_{right_neighbor}']['longside']
            endX = nx + spacing[right_neighbor][f'against_{next_boundary_against[0][0]}']['longside'] - _spacing
            if endX > x + X:
                new_main_zone = (origin, (endX - x, Y))
    return boundary_against, new_main_zone

def bound_in_general(main_door, boundary, main_zones, desk_orientations4main_zones, passageway_locations4main_zones, upbounds, 
                     boundary_against_in_Y_axis4main_zones, boundary_against4main_zones,
                     sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, 
                     num_of_storage_in_axises4main_zones, num_of_printer_sets_in_axises4main_zones, 
                     printer_sets4sub_zones, 
                     num_of_accompaniment_seats4main_zones, individual, 
                     unfold=False,
                     inputs4global_layout=None,
                     inputs4local_layout=None, var_num_of_low_cabinets4main_zones=None, var_num_of_small_lockers4main_zones=None):

    upbounds4main_zones, upbounds4sub_zones = upbounds

    total_num_of_low_cabinets, total_num_of_small_lockers = 0, 0

    num_of_printer_sets_near_walls4sub_zones = []
    num_of_printer_sets_near_walls4main_zones = []
    relative_plmts4printer_sets_and_storage4main_zones = []
    RECTs_dict = defaultdict(list)
    rectangles_dict = defaultdict(list)
    components_dict = defaultdict(list)
    num_of_subjects_per_col4main_zones = []

    updated_main_zones = []
    _boundary_against4updated_main_zones = []
    total_overbounds_of_parallel2x4storage, total_overbounds_of_storage, total_overbounds_of_printer_sets = 0, 0, 0
    assigned_num_of_accompaniment_seats_list = []
    total_insufficiency_of_accompaniment_seats, total_bound_in_accompaniment_seats_without_islands = 0, 0
    num_of_persons = 0
    overbounds_within_main_zones = 0
    total_overbounds_of_high_cabinets_near_wall = 0
    num_of_islands4storage_list = []
    k, delta = 0, 3
    index4main_zones = (k, delta)
    for i, (main_zone, desk_orientation, passageway_location, comp_upbounds, 
            boundary_against_in_Y_axis, boundary_against, 
            num_of_storage_in_axises4main_zone, num_of_printer_sets_in_axises4main_zone,
            num_of_accompaniment_seats) in enumerate(zip(main_zones, desk_orientations4main_zones, passageway_locations4main_zones, upbounds4main_zones, 
                                                            boundary_against_in_Y_axis4main_zones, boundary_against4main_zones,
                                                            num_of_storage_in_axises4main_zones, num_of_printer_sets_in_axises4main_zones,
                                                            num_of_accompaniment_seats4main_zones)):
        partial_individual = individual[k:k+delta]
        # num_of_two_col_islands, _, has_mixed_islands, *_ = partial_individual

        new_boundary_against, new_main_zone = deepcopy(boundary_against), deepcopy(main_zone)
        # if i > 0:
        #     new_boundary_against, new_main_zone = _extend_left_boundary(new_main_zone, partial_individual, new_boundary_against,
        #                                                                 updated_main_zones[i-1], individual[k-delta:k], RECTs_dict['main_zones'][i-1], boundary_against4main_zones[i-1])
        # if i < len(main_zones) - 1:
        #     new_boundary_against, new_main_zone = _extend_right_boundary(new_main_zone, partial_individual, new_boundary_against,
        #                                                                  main_zones[i+1], individual[k+delta:k+2*delta], boundary_against4main_zones[i+1])

        if inputs4local_layout:
            var_num_of_low_cabinets4main_zone, var_num_of_small_lockers4main_zone = (var_num_of_low_cabinets4main_zones[i], var_num_of_small_lockers4main_zones[i]) 
        else:
            var_num_of_low_cabinets4main_zone, var_num_of_small_lockers4main_zone = (None, None)
       
        num_of_low_cabinets, num_of_small_lockers, \
        _components_dict, _rectangles_dict, RECTs, \
            partial_individual, num_of_printer_sets_near_walls, relative_plmts4printer_sets_and_storage4main_zone, num_of_subjects_per_col, \
                updated_main_zone, _boundary_against4updated_main_zone, \
            overbounds_of_parallel2x4storage, overbounds_of_storage, overbounds_of_printer_sets, \
            assigned_num_of_accompaniment_seats, insufficiency_of_accompaniment_seats, bound_in_accompaniment_seats_without_islands,\
            num_of_overbounds, overbounds_of_high_cabinets_near_wall = bound_main_zone(main_door, main_zone, new_main_zone, desk_orientation, passageway_location, comp_upbounds, partial_individual, 
                                                                                       num_of_storage_in_axises4main_zone, num_of_printer_sets_in_axises4main_zone, 
                                                                                       num_of_accompaniment_seats, 
                                                                                       boundary_against_in_Y_axis, new_boundary_against, 
                                                                                       inputs4global_layout=inputs4global_layout,
                                                                                       inputs4local_layout=inputs4local_layout, var_num_of_low_cabinets=var_num_of_low_cabinets4main_zone, var_num_of_small_lockers=var_num_of_small_lockers4main_zone,
                                                                                       unfold=unfold)  
       
        if inputs4local_layout:
            total_num_of_low_cabinets += num_of_low_cabinets
            total_num_of_small_lockers += num_of_small_lockers

        num_of_printer_sets_near_walls4main_zones.append(num_of_printer_sets_near_walls)
        updated_main_zones.append(updated_main_zone)
        _boundary_against4updated_main_zones.append(_boundary_against4updated_main_zone)

        total_overbounds_of_parallel2x4storage += overbounds_of_parallel2x4storage
        total_overbounds_of_storage += overbounds_of_storage
        total_overbounds_of_printer_sets += overbounds_of_printer_sets

        assigned_num_of_accompaniment_seats_list.append(assigned_num_of_accompaniment_seats)
        total_insufficiency_of_accompaniment_seats += insufficiency_of_accompaniment_seats
        total_bound_in_accompaniment_seats_without_islands += bound_in_accompaniment_seats_without_islands

        overbounds_within_main_zones += num_of_overbounds
        # if boundary_against[0] == 'two_col_islands' and RECTs[-2]:
        # if boundary_against[0] == 'islands' and RECTs[-2]:
        #     (x, y), (X, Y) = RECTs[-2]
        #     if x + X <= main_zone[0][0]:
        #         overbounds_within_main_zones += 1
        
        total_overbounds_of_high_cabinets_near_wall += overbounds_of_high_cabinets_near_wall

        num_of_two_col_islands, _, has_mixed_islands, *_ = partial_individual
        if num_of_accompaniment_seats == 0:
            num_of_persons += num_of_two_col_islands * num_of_subjects_per_col['desk']*2 + has_mixed_islands * num_of_subjects_per_col['desk']
        else:
            num_of_persons += sum([num*2 for num in num_of_subjects_per_col['desk']]) if type(num_of_subjects_per_col['desk']) is list else num_of_two_col_islands * num_of_subjects_per_col['desk']*2
            if has_mixed_islands:
                num_of_persons += num_of_subjects_per_col['mixed_desk']
        # if num_of_mixed_islands:
        #     _num_of_persons_in_mixed_col = int(num_of_subjects_per_col['desk'] / 3) * 3
        #     num_of_persons += _num_of_persons_in_mixed_col

        num_of_islands4storage_list.append(has_mixed_islands + num_of_two_col_islands)

        num_of_subjects_per_col4main_zones.append(num_of_subjects_per_col)

        relative_plmts4printer_sets_and_storage4main_zones.append(relative_plmts4printer_sets_and_storage4main_zone)
        RECTs_dict['main_zones'].append(RECTs)
        rectangles_dict['main_zones'].append(_rectangles_dict)
        components_dict['main_zones'].append(_components_dict)

        k += delta


    overbounds_within_sub_zones = 0
    delta = 6
    index4sub_zones = (k, delta)
    for sub_zone, storage_orientation, wall_location, printer_sets4sub_zone, upbounds4sub_zone in zip(sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, 
                                                                                                      printer_sets4sub_zones, upbounds4sub_zones):
        partial_individual = individual[k:k+delta]
        _components_dict, _rectangles_dict, num_of_printer_sets_near_walls, *RECTs, \
            overbounds_of_printer_sets, num_of_overbounds = bound_sub_zone(sub_zone, storage_orientation, wall_location, partial_individual, 
                                                                            printer_sets4sub_zone, upbounds4sub_zone, unfold=unfold)
        total_overbounds_of_printer_sets += overbounds_of_printer_sets
        overbounds_within_sub_zones += num_of_overbounds
        
        num_of_printer_sets_near_walls4sub_zones.append(num_of_printer_sets_near_walls)
        RECTs_dict['sub_zones'].append(*RECTs)
        rectangles_dict['sub_zones'].append(_rectangles_dict)
        components_dict['sub_zones'].append(_components_dict)
        k += delta

    return total_num_of_low_cabinets, total_num_of_small_lockers,\
            components_dict, rectangles_dict, RECTs_dict, \
            num_of_printer_sets_near_walls4sub_zones, num_of_printer_sets_near_walls4main_zones, relative_plmts4printer_sets_and_storage4main_zones, \
           _boundary_against4updated_main_zones, \
           total_overbounds_of_parallel2x4storage, total_overbounds_of_storage, total_overbounds_of_printer_sets, \
           assigned_num_of_accompaniment_seats_list, total_insufficiency_of_accompaniment_seats, total_bound_in_accompaniment_seats_without_islands, \
           overbounds_within_main_zones, overbounds_within_sub_zones, total_overbounds_of_high_cabinets_near_wall, \
           num_of_persons, num_of_subjects_per_col4main_zones, num_of_islands4storage_list, (index4main_zones, index4sub_zones)

