from copy import deepcopy

from .bound_sub_model import _get_spacing_between, __get_boundary_side_in_Y_axis

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from general.configs import spacing, sizes
from general.latest_spacing import spacing as latest_spacing, __map_side_to_index
from general.utils import _calcu_occupied_length_for_subjects


def __calcu_maxY_in_X_axis(relative_num4storage_in_X_axis, _num_of_printer_sets_in_axis, max_or_min=max):
    k, delta = 0, 3
    plmts_in_X_axis = {subject : list(relative_num4storage_in_X_axis[delta*i:delta*i+delta]) for i, subject in enumerate(['big_lockers', 'high_cabinets'])}    
    
    l, w = sizes['storage']
    Ys4storage_in_X_axis = {(comp, parallel2x): 0 if nrows * ncols == 0 else _calcu_occupied_length_for_subjects(comp, nrows, w, near_wall=True) if parallel2x else l * ncols 
                            for comp, (parallel2x, nrows, ncols) in plmts_in_X_axis.items()}
    maxY4storage_in_X_axis = max_or_min(Ys4storage_in_X_axis.values())

    l, w = sizes['printer_set']
    maxY_in_X_axis = max_or_min(maxY4storage_in_X_axis, w if _num_of_printer_sets_in_axis > 0 else 0)

    Ys_in_X_axis = deepcopy(Ys4storage_in_X_axis)
    Ys_in_X_axis[('printer_set', True)] = w if _num_of_printer_sets_in_axis > 0 else 0
    component_with_maxY = [(component if component == 'printer_set' else 'storage', parallel2x) 
                            for (component, parallel2x), Y in Ys_in_X_axis.items() if Y == maxY_in_X_axis][0]
    return maxY_in_X_axis, component_with_maxY


# def __starts_from_wall_origin(wall, maxY_in_X_axis, component_with_maxY, 
#                                 remained_walls_in_X_axis, maxYs_in_X_axis):
#     res = wall in remained_walls_in_X_axis.keys() and remained_walls_in_X_axis[wall] >= maxY_in_X_axis + _get_spacing_between(component_with_maxY, maxYs_in_X_axis[wall])
#     return res

# __get_boundary_side_in_Y_axis = lambda parallel2x: __map_side_to_index('shortside' if not parallel2x else 'longside')

def _determine_zone_for_intersected_placements(wall, relative_num4storage_in_X_axis, _num_of_printer_sets_in_axis, 
                                                remained_walls_in_X_axis, maxYs_in_X_axis, 
                                                updated_relative_main_zone, relative_main_zone,
                                                latest_spacing=latest_spacing):
    maxY_in_X_axis, component_with_maxY = __calcu_maxY_in_X_axis(relative_num4storage_in_X_axis, _num_of_printer_sets_in_axis)

    # component, parallel2x = component_with_maxY
    # if maxY_in_X_axis == 0:
    #     component = 'wall'
    #     parallel2x = True if wall in ['down', 'up'] else False
    # else:
    #     if wall in ['left', 'right']:
    #         parallel2x = not parallel2x
    # component_with_maxY = (component, parallel2x)


    zone = deepcopy(updated_relative_main_zone)
    if wall == 'down':
        zone = deepcopy(relative_main_zone)
    elif wall == 'left':
        if 'down' in maxYs_in_X_axis.keys() and maxYs_in_X_axis['down'][0] == 0:
            zone = deepcopy(relative_main_zone)

    elif wall == 'right':
        if 'down' in remained_walls_in_X_axis.keys() and remained_walls_in_X_axis['down'] >= maxY_in_X_axis + _get_spacing_between(component_with_maxY, (maxYs_in_X_axis['down'][1][0], not maxYs_in_X_axis['down'][1][1]), __get_boundary_side=__get_boundary_side_in_Y_axis):
            (x, _), (X, _) = updated_relative_main_zone
            (_, y), (_, Y) = relative_main_zone
            zone = ((x, y), (X, Y))
    elif wall == 'up':
        (x, y), (X, Y) = updated_relative_main_zone
        starting_from_left, ending_to_right = 'left' in remained_walls_in_X_axis.keys() and remained_walls_in_X_axis['left'] >= maxY_in_X_axis + _get_spacing_between(component_with_maxY, maxYs_in_X_axis['left'][1], __get_boundary_side=__get_boundary_side_in_Y_axis), \
                                                'right' in remained_walls_in_X_axis.keys() and remained_walls_in_X_axis['right'] >= maxY_in_X_axis + _get_spacing_between(component_with_maxY, maxYs_in_X_axis['right'][1], __get_boundary_side=__get_boundary_side_in_Y_axis)
        if starting_from_left and ending_to_right:
            (x, _), (X, _) = relative_main_zone
        elif starting_from_left:
            (x, _), (X, _) = relative_main_zone
            X -= maxYs_in_X_axis['right'][0]
        elif ending_to_right:
            (x, _), (X, _) = updated_relative_main_zone
            X += maxYs_in_X_axis['right'][0]
        zone = ((x, y), (X, Y))
    return (maxY_in_X_axis, component_with_maxY), zone

    
def _determine_neighbors_for_zone_in_X_axis(wall, maxY_in_X_axis, component_with_maxY,
                                            remained_walls_in_X_axis, maxYs_in_X_axis, neighbors=None):
    if neighbors is None:
        neighbors = [('wall', False if wall in ['down', 'up'] else True)]*2
    elif type(neighbors) == tuple:
        neighbors = list(neighbors)

    if wall == 'down':
        neighbors = neighbors
    elif wall == 'left':
        if 'down' in maxYs_in_X_axis.keys() and maxYs_in_X_axis['down'][0] > 0:
            neighbors[0] = maxYs_in_X_axis['down'][1]
    elif wall == 'right':
        if 'down' in remained_walls_in_X_axis.keys() and remained_walls_in_X_axis['down'] < maxY_in_X_axis + _get_spacing_between(component_with_maxY, (maxYs_in_X_axis['down'][1][0], not maxYs_in_X_axis['down'][1][1]), __get_boundary_side=__get_boundary_side_in_Y_axis):
            neighbors[0] = maxYs_in_X_axis['down'][1]
    elif wall == 'up':
        starting_from_left, ending_to_right = 'left' in remained_walls_in_X_axis.keys() and remained_walls_in_X_axis['left'] >= maxY_in_X_axis +  _get_spacing_between(component_with_maxY, maxYs_in_X_axis['left'][1], __get_boundary_side=__get_boundary_side_in_Y_axis), \
                                                'right' in remained_walls_in_X_axis.keys() and remained_walls_in_X_axis['right'] >= maxY_in_X_axis +  _get_spacing_between(component_with_maxY, maxYs_in_X_axis['right'][1], __get_boundary_side=__get_boundary_side_in_Y_axis)
        if starting_from_left and ending_to_right:
            neighbors = neighbors
        elif starting_from_left:
            neighbors[1] = maxYs_in_X_axis['right'][1]
        elif ending_to_right:
            neighbors[0] = maxYs_in_X_axis['left'][1]
        else:
            neighbors = (maxYs_in_X_axis['left'][1], maxYs_in_X_axis['right'][1])
    return neighbors


def _calcu_remained_wall_in_X_axis(_num_of_printer_sets_in_axis, relative_plmt_results4printer_sets,
                                    relative_num4storage_in_X_axis, relative_plmt_results4storage,
                                    relative_shifted_zone4both_in_X_axis, 
                                    subject_at_head='wall', subject_at_tail='wall'):
    _, (X, _) = relative_shifted_zone4both_in_X_axis
    remained_wall_in_X_axis = X
    if _num_of_printer_sets_in_axis >= 2:
        remained_wall_in_X_axis = 0
        # subject_at_head, subject_at_tail = [('printer_set', True)]*2
    else:
        endX = None
        _get_endX = lambda RECT: sum(RECT[i][0] for i in range(2))
        if _num_of_printer_sets_in_axis > 0:
            # subject_at_head = ('printer_set', True)

            rectangles4printer_sets, _ = relative_plmt_results4printer_sets
            for rectangle, _ in rectangles4printer_sets:
                curr_endX = _get_endX(rectangle)
                if endX is None or endX < curr_endX:
                    endX = curr_endX
        if any(nrows * ncols != 0 for _, nrows, ncols in [relative_num4storage_in_X_axis[:3], relative_num4storage_in_X_axis[3:]]):
            plmts_in_partitions, RECTs_in_partitions = relative_plmt_results4storage

            # for plmts in plmts_in_partitions:
            #     for subject, (parallel2x, nrows, ncols) in plmts.items():
            #         if nrows * ncols == 0: continue

            #         _parallel2x = parallel2x if wall in ['down', 'up'] else not parallel2x
            #         if subject_at_head is None:
            #             subject_at_head = (subject, _parallel2x)
            #         subject_at_tail = (subject, _parallel2x)

            for RECTs in RECTs_in_partitions:
                for RECT in RECTs:
                    curr_endX = _get_endX(RECT)
                    if endX is None or endX < curr_endX:
                        endX = curr_endX
        if endX is not None:
            remained_wall_in_X_axis = _get_endX(relative_shifted_zone4both_in_X_axis) - endX

    # return (subject_at_head, subject_at_tail), remained_wall_in_X_axis
    return remained_wall_in_X_axis