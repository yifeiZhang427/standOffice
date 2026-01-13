from copy import deepcopy
from collections import defaultdict
from itertools import chain

from .transform import transform_RECTs, transform_components
from .unfold_RECTs_into_rows import unfold_RECTs_in_sub_zone, unfold_RECTs_in_partitions
from .unfold_rows_into_components import unfold_components_in_sub_zone, __unfold_a_partitioned_row_of_printer_sets
from .unfold_RECTs_into_rows import yield_shifts_for_subjects, _unfold_RECT_into_rows

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from general.configs import spacing, spacing_in_4D, sizes, rotations_of_directions
from general.latest_spacing import spacing as latest_spacing, __map_side_to_index, main_passageway_width, additional_spacing2door
from general.utils import _calcu_occupied_length_for_subjects, _calcu_nrows4subjects, calcu_max_matrix_within_zone4subjects


def _get_RECT4subjects(subject, parallel2x, nrows, ncols, sizes=sizes):
    l, w = sizes['storage']
    row_length = _calcu_occupied_length_for_subjects(subject, nrows, w)
    col_length = ncols * l
    RECT = (col_length, row_length) if parallel2x else (row_length, col_length)
    return RECT


def __get_uniform_distribution(num_of_printer_sets, rotation, origin, XY, parallel2x, latest_spacing=latest_spacing, sizes=sizes):
    l, w = sizes['printer_set']

    X, Y = XY
    mean_spacing = 0 if num_of_printer_sets <= 1 else int(((X if parallel2x else Y) - l * num_of_printer_sets) / (num_of_printer_sets - 1))
    shortside_index = __map_side_to_index('shortside')
    self_spacing = latest_spacing['printer_set']['against_printer_set'][shortside_index][shortside_index]
    if mean_spacing > self_spacing:
        self_spacing = mean_spacing

    x, y = origin
    # rectangles = [(((x + (l + self_spacing) * j, y), (l, w)), rotation) if parallel2x else 
    #               (((x, y + (l + self_spacing) * j), (w, l)), rotation)
    #               for j in range(num_of_printer_sets)]
    rectangles = []
    for j in range(num_of_printer_sets):
        if parallel2x:
            (_x, _y), (_X, _Y) = ((x + (l + self_spacing) * j, y), (l, w)) 
            if _x + _X > x + X: continue
        else:
            (_x, _y), (_X, _Y) = ((x, y + (l + self_spacing) * j), (w, l))
            if _y + _Y > y + Y: continue
        rectangles.append((((_x, _y), (_X, _Y)), rotation))
        
    return rectangles


_get_endX = lambda RECT : sum(RECT[i][0] for i in range(2))
__get_boundary_side_in_X_axis = lambda parallel2x: __map_side_to_index('shortside' if parallel2x else 'longside')
__get_boundary_side_in_Y_axis = lambda parallel2x: __map_side_to_index('shortside' if not parallel2x else 'longside')

# _get_storage_spacing_against_boundary = lambda storage_parallel2x, boundary, storage_spacing: \
#                                             storage_spacing[f'against_{boundary[0]}'][__get_boundary_side(storage_parallel2x)] if boundary[0] in ['wall', 'window', 'main_passageway'] else \
#                                             storage_spacing[f'against_{boundary[0]}'][__get_boundary_side(storage_parallel2x)][__get_boundary_side(boundary[1])]

def __map_virtual_boundary(virtual_boundary):
    virtual2real = {
        'office_wall': 'main_passageway',
        'islands': 'main_passageway',
        'virtual_wall4local_layout': 'main_passageway'
    }
    if virtual_boundary in virtual2real.keys():
        return virtual2real[virtual_boundary]
    else:
        return virtual_boundary
    
def _get_spacing_between(subject, target, latest_spacing=latest_spacing, __get_boundary_side=__get_boundary_side_in_X_axis,
                         main_passageway_width=main_passageway_width, sizes=sizes):
    (_subject, parallel2x_of_subject), (_target, parallel2x_of_target) = subject, target
    __subject, __target = _subject, _target
    _subject = __map_virtual_boundary(_subject)
    _target = __map_virtual_boundary(_target)
    
    if f'against_{_target}' not in latest_spacing[_subject].keys():
        (_subject, parallel2x_of_subject), (_target, parallel2x_of_target) = target, subject

    resulting_spacing = latest_spacing[_subject][f'against_{_target}'][__get_boundary_side(parallel2x_of_subject)]
    if _target not in ['wall', 'window', 'main_passageway', 'door']:
        resulting_spacing = resulting_spacing[__get_boundary_side(parallel2x_of_target)]

    if _target == 'main_passageway' and __target == 'virtual_wall4local_layout':
        resulting_spacing += sizes['chair'][1]
    elif _target == 'main_passageway' and __target == 'office_wall':
        resulting_spacing += main_passageway_width
    elif _target == 'door':
        resulting_spacing += additional_spacing2door
    return resulting_spacing


def _reduce_by(num, _num):
    _by = 0
    while num > 0 and _num > 0:
        _by += 1
        num -= 1
        _num -= 1
    return _by

def place_storage_within_zone(_remained_plmts, zone, _boundary_against, 
                              _boundary_against_in_Y_axis=None,
                              sizes=sizes):
    _boundary_against_in_Y_axis = None
    
    plmts_within_zone = {}
    RECTs_within_zone = []

    remained_zone = deepcopy(zone)
    l, w = sizes['storage']
    for subject in ['big_lockers', 'high_cabinets']:
        parallel2x, nrows, ncols = _remained_plmts[subject]
        if nrows * ncols == 0: continue

        left_spacing, right_spacing = [_get_spacing_between(('storage', parallel2x), boundary) for boundary in _boundary_against]
        (x, y), (X, Y) = remained_zone
        remained_BOX = ((x + left_spacing, y), (X - left_spacing - right_spacing, Y))
        # if X <= 0: continue

        if parallel2x:
            if _boundary_against_in_Y_axis is None:
                _nrows = nrows
            else:
                _, up_spacing = [_get_spacing_between(('storage', parallel2x), boundary, 
                                                      __get_boundary_side=__get_boundary_side_in_Y_axis) for boundary in _boundary_against_in_Y_axis]
                _nrows = _calcu_nrows4subjects(subject, sizes['storage'][1], Y - up_spacing)

            _, (X, _) = remained_BOX
            if X <= 0: continue

            _ncols = int(X / l)
            _by = _reduce_by(ncols, _ncols)
            XY = _get_RECT4subjects(subject, parallel2x, _nrows, _by)
            plmts_within_zone[subject] = (parallel2x, _nrows, _by)
            _remained_plmts[subject][-1] -= _by

            deltaX = l * _by
        else:
            if _boundary_against_in_Y_axis is None:
                _ncols = ncols
            else:
                _, up_spacing = [_get_spacing_between(('storage', parallel2x), boundary, 
                                        __get_boundary_side=__get_boundary_side_in_Y_axis) for boundary in _boundary_against_in_Y_axis]
                _ncols = int((Y - up_spacing) / sizes['storage'][0])

            (left_neighbor, _), _ = _boundary_against
            near_wall = True if left_neighbor == 'wall' else False
            if near_wall:
                (x, y), (X, Y) = remained_BOX
                remained_BOX = ((x - left_spacing, y), (X + left_spacing, Y))

            _, (X, _) = remained_BOX
            if X <= 0: continue

            _, (X, _) = remained_BOX
            _nrows = _calcu_nrows4subjects(subject, w, X, near_wall=near_wall)
            _by = _reduce_by(nrows, _nrows)
            XY = _get_RECT4subjects(subject, parallel2x, _by, _ncols)
            plmts_within_zone[subject] = (parallel2x, _by, _ncols)
            _remained_plmts[subject][-2] -= _by

            deltaX = _calcu_occupied_length_for_subjects(subject, _by, w, near_wall=near_wall)

        if _by > 0 or deltaX:
            RECT = (remained_BOX[0], XY)
            RECTs_within_zone.append(RECT)
            (x, y), (X, Y) = remained_BOX
            remained_zone = ((x + deltaX, y), (_get_endX(remained_zone) - x - deltaX, Y))
            _boundary_against = (('storage', parallel2x), _boundary_against[-1])
        
    return plmts_within_zone, RECTs_within_zone


def _reduce_storage_by_rows(subject, max_nrows, max_ncols, _unit, remained_storage):
    nrows = 0
    while remained_storage[subject] > 0 and max_nrows > 0 and max_ncols > 0:
        remained_storage[subject] -= 1 * max_ncols * _unit[subject]
        max_nrows -= 1
        nrows += 1
    return nrows


def place_storage_for_each_plmt_comb_within_zone(each_plmt_comb, zone, _boundary_against, 
                                                partial_plmt=None,
                                                sizes=sizes):
    max_plmts_within_zone = {}

    remained_zone = deepcopy(zone)
    l, w = sizes['storage']
    for subject, parallel2x in each_plmt_comb.items():
        if '_' in subject:
            _subject = subject.split('_')[-1][:-1]
        # if _remained_storage[_subject] <= 0: continue

        left_spacing, right_spacing = [_get_spacing_between(('storage', parallel2x), boundary) for boundary in _boundary_against]
        (x, y), (X, Y) = remained_zone
        remained_BOX = ((x + left_spacing, y), (X - left_spacing - right_spacing, Y))
        # if X <= 0: continue

        if parallel2x:
            near_wall = True
        else:
            (left_neighbor, _), _ = _boundary_against
            near_wall = True if left_neighbor == 'wall' else False
            if near_wall:
                (x, y), (X, Y) = remained_BOX
                remained_BOX = ((x - left_spacing, y), (X + left_spacing, Y))

        _, (X, _) = remained_BOX
        if X <= 0: 
            max_plmts_within_zone[subject] = (parallel2x, 0, 0)
            continue
            
        if partial_plmt and subject in partial_plmt.keys():
            _, nrows, ncols = partial_plmt[subject]
        else:
            nrows, ncols = calcu_max_matrix_within_zone4subjects(subject, parallel2x, remained_BOX[1], near_wall=near_wall)
        # nrows = _reduce_storage_by_rows(_subject, max_nrows, max_ncols, _unit, _remained_storage)
        # max_plmts_within_zone[subject] = (parallel2x, nrows, max_ncols)

        # deltaX = max_ncols * l if parallel2x else _calcu_occupied_length_for_subjects(subject, nrows, w, near_wall=near_wall)

        if parallel2x:
            deltaX = ncols * l
            max_plmts_within_zone[subject] = (parallel2x, None, ncols)
        else:
            deltaX = _calcu_occupied_length_for_subjects(subject, nrows, w, near_wall=near_wall)
            max_plmts_within_zone[subject] = (parallel2x, nrows, None)
        (x, y), (X, Y) = remained_BOX
        remained_zone = ((x + deltaX, y), (_get_endX(remained_zone) - x - deltaX, Y))
        _boundary_against = (('storage', parallel2x), _boundary_against[-1])
        
    return max_plmts_within_zone


def _place_printer_sets_in_XY_axises(sub_zone, printer_sets4sub_zone, relative_origin=(0, 0),
                                    _default_boundary_against=None,
                                     sizes=sizes, rotations_of_directions=rotations_of_directions):

    partitioned_zones, boundary_against4partitioned_zones = [], []
    rectangles4printer_sets = []

    _parallel2x_of_printers, num_of_printer_sets = printer_sets4sub_zone
    if _default_boundary_against is None:
        _wall_boundary = ('wall', False)
        _default_boundary_against = tuple([_wall_boundary] * 2)
    else:
        __default_boundary_against = list(_default_boundary_against)
        for i in range(len(__default_boundary_against)):
            _boundary, with_door = __default_boundary_against[i]
            if with_door and _boundary == 'wall':
                __default_boundary_against[i] = ('door', with_door)
        _default_boundary_against = __default_boundary_against

    _printer_set_boundary = ('printer_set', _parallel2x_of_printers)

    l, w = sizes['printer_set']
    relative_origin, (X, Y) = sub_zone
    x, y = relative_origin
    if num_of_printer_sets > 0:
        if _parallel2x_of_printers:
            # rectangles4printer_sets = [(((x + l * j, y), (l, w)), rotations_of_directions['up']) for j in range(num_of_printer_sets)]
            # relative_origin = (x + l * num_of_printer_sets, y)
            # endX = relative_origin[0] + spacing['printer_set']['against_wall']['shortside']

            left_spacing, right_spacing = [_get_spacing_between(_printer_set_boundary, boundary) for boundary in _default_boundary_against]
            # x += left_spacing
            # X -= left_spacing + right_spacing
            rectangles4printer_sets = __get_uniform_distribution(num_of_printer_sets, rotations_of_directions['up'],
                                                                 (x + left_spacing, y), (X - left_spacing - right_spacing, Y), True)
            
            # if num_of_printer_sets == 1:
            if len(rectangles4printer_sets) == 1:
                _endX = _get_endX(rectangles4printer_sets[0][0])
                partitioned_zones = [((_endX, y), (x + X - _endX, Y))]
                boundary_against4partitioned_zones = [(_printer_set_boundary, _default_boundary_against[1])]
            elif len(rectangles4printer_sets) > 1:
                for printer_set0, printer_set1 in zip(rectangles4printer_sets, rectangles4printer_sets[1:]):
                    _endX0 = _get_endX(printer_set0[0])
                    ((x1, _), _), _ = printer_set1
                    interval_zone = ((_endX0, y), (x1 - _endX0, Y))
                    _boundary_against = tuple([_printer_set_boundary] * 2)
                    partitioned_zones.append(interval_zone)
                    boundary_against4partitioned_zones.append(_boundary_against)
            else:
                partitioned_zones = [sub_zone]
                boundary_against4partitioned_zones = [_default_boundary_against]  
        else:
            # rectangles4printer_sets = [(((x, y + l * j), (w, l)), rotations_of_directions['right']) for j in range(num_of_printer_sets)]
            # relative_origin = (x + w, y)
            # endX = relative_origin[0] + spacing['printer_set']['against_wall']['longside']
            down_spacing, up_spacing = [_get_spacing_between(_printer_set_boundary, boundary, __get_boundary_side=__get_boundary_side_in_Y_axis) for boundary in _default_boundary_against]
            # y += down_spacing
            # Y -= down_spacing + up_spacing
            rectangles4printer_sets = __get_uniform_distribution(num_of_printer_sets, rotations_of_directions['right'],
                                                                 (x, y + down_spacing), (X, Y - down_spacing - up_spacing), False)
            if len(rectangles4printer_sets) > 0:
                partitioned_zones = [((x + w, y), (x + X - w, Y))]
                boundary_against4partitioned_zones = [(_printer_set_boundary, _default_boundary_against[1])]
                relative_origin = (x + w, y)
            else:
                partitioned_zones = [sub_zone]
                boundary_against4partitioned_zones = [_default_boundary_against]  
    else:
        partitioned_zones = [sub_zone]
        boundary_against4partitioned_zones = [_default_boundary_against]
    
    num_of_printer_sets = len(rectangles4printer_sets)
    return num_of_printer_sets, rectangles4printer_sets, partitioned_zones, boundary_against4partitioned_zones


__sum_up = lambda subject, parallel2x, nrows, ncols, plmts_in_partitions: (parallel2x, nrows, sum(plmts[subject][-1] if subject in plmts.keys() else 0 for plmts in plmts_in_partitions)) if parallel2x else \
                                                                            (parallel2x, sum(plmts[subject][-2] if subject in plmts.keys() else 0 for plmts in plmts_in_partitions), ncols)

def _place_storage_in_partitioned_zones(partial_individual, partitioned_zones, boundary_against4partitioned_zones, 
                                        _boundary_against_in_Y_axis4main_zone=None):
    k, delta = 0, 3
    plmts = {subject : list(partial_individual[delta*i:delta*i+delta]) for i, subject in enumerate(['big_lockers', 'high_cabinets'])}

    plmts_in_partitions, RECTs_in_partitions = [], []
    remained_plmts = deepcopy(plmts)
    for zone, _boundary_against in zip(partitioned_zones, boundary_against4partitioned_zones):
        plmts_within_zone, RECTs_within_zone = place_storage_within_zone(remained_plmts, zone, _boundary_against, 
                                                                         _boundary_against_in_Y_axis=_boundary_against_in_Y_axis4main_zone)
        plmts_in_partitions.append(plmts_within_zone)
        RECTs_in_partitions.append(RECTs_within_zone)

    summed_plmts = {subject: __sum_up(subject, *plmt, plmts_in_partitions) for subject, plmt in plmts.items()}
    return summed_plmts, plmts_in_partitions, RECTs_in_partitions, remained_plmts

def _bound_in_storage_placements(plmts, upbounds4sub_zone, remained_plmts):
    num_of_overbounds = 0
    for subject, (parallel2x, nrows, ncols) in plmts.items():
        max_nrows, max_ncols = upbounds4sub_zone[subject][parallel2x]
        if nrows > max_nrows or ncols > max_ncols:
            num_of_overbounds = 1
            break
    if any(nrows * ncols != 0 for _, nrows, ncols in remained_plmts.values()):
        num_of_overbounds = 1
    return num_of_overbounds

def _bound_sub_zone_in_XY_axises(partial_individual, upbounds4sub_zone, 
                                 printer_sets4sub_zone, partitioned_zones, boundary_against4partitioned_zones):
                                # sub_zone, 
                                #  relative_origin=(0, 0),
                                #  spacing=spacing, sizes=sizes, rotations_of_directions=rotations_of_directions):
    summed_plmts, plmts_in_partitions, RECTs_in_partitions, remained_plmts = _place_storage_in_partitioned_zones(partial_individual, partitioned_zones, boundary_against4partitioned_zones)

    k, delta = 0, 3
    plmts = {subject : list(partial_individual[delta*i:delta*i+delta]) for i, subject in enumerate(['big_lockers', 'high_cabinets'])}
    num_of_overbounds = _bound_in_storage_placements(plmts, upbounds4sub_zone, remained_plmts)


    # x, y = relative_origin
    # endX = x
    
    # ox, oy = relative_origin
    # RECTs = []
    # rectangles_dict = defaultdict(list)
    # prev_subjects = 0
    # k, delta = 0, 3
    # for i, subject in enumerate(['big_lockers', 'high_cabinets']):
    #     parallel2x, nrows, ncols = partial_individual[k:k+delta]
    #     XY = _get_RECT4subjects(subject, parallel2x, nrows, ncols)

    #     if nrows * ncols > 0:
    #         if i == 0:
    #             if num_of_printer_sets > 0:
    #                 ox += spacing['storage']['against_printer_set']['shortside' if _parallel2x_of_printers else 'longside']
    #         else:
    #             if prev_subjects[-2] * prev_subjects[-1] > 0:
    #                 if parallel2x != prev_subjects[0]:
    #                     ox += spacing['storage']['against_storage']['longside']
    #                 elif parallel2x:
    #                     ox += spacing['storage']['against_storage']['shortside']
            
    #     RECT = ((ox, oy), XY)
    #     RECTs.append(RECT)

    #     ox += XY[0]
    #     if nrows * ncols > 0:
    #         endX = ox + spacing['storage']['against_wall']['shortside' if parallel2x else 'longside']
    #     prev_subjects = (parallel2x, nrows, ncols)
    #     k += delta
    
    # # _get_end_point = lambda RECT: sum(RECT[i][0] for i in range(2))
    # combined_RECT = (endX, max(RECTs[i][1][1] for i in range(2)))
    # boundary_RECT = sub_zone[1]
    
    # num_of_overbounds = 0
    # for length, bound in zip(combined_RECT, boundary_RECT):
    #     if length > bound:
    #         num_of_overbounds += 1

    _parallel2x_of_printers, num_of_printer_sets = printer_sets4sub_zone
    overbounds_of_printer_sets = 1 if num_of_printer_sets > upbounds4sub_zone['printer_sets'][_parallel2x_of_printers][-1] else 0
    return (summed_plmts, plmts_in_partitions, RECTs_in_partitions), overbounds_of_printer_sets, num_of_overbounds
    # return rectangles4printer_sets, (plmts_in_partitions, RECTs_in_partitions, boundary_against4partitioned_zones), overbounds_of_printer_sets, num_of_overbounds


def _transform_into_XY_axises(sub_zone, storage_orientation, upbounds4sub_zone, partial_individual, printer_sets4sub_zone):
    _, (X, Y) = sub_zone
    if storage_orientation:
        rotated_sub_zone = ((0, 0), (Y, X))
        rotated_upbounds4sub_zone = {subject: upbound[::-1] if type(upbound) is list else upbound for subject, upbound in upbounds4sub_zone.items()}
        resulting_partial_individual = list(deepcopy(partial_individual))
        delta = 3
        for i in range(2):
            resulting_partial_individual[i*delta] = (resulting_partial_individual[i*delta] + 1) % 2

        parallel2x, ncols = printer_sets4sub_zone
        rotated_printer_sets4sub_zone = ((parallel2x + 1) % 2, ncols)
    else:
        rotated_sub_zone = ((0, 0), (X, Y))
        rotated_upbounds4sub_zone = upbounds4sub_zone
        resulting_partial_individual = partial_individual
        rotated_printer_sets4sub_zone = printer_sets4sub_zone
    return rotated_sub_zone, rotated_upbounds4sub_zone, resulting_partial_individual, rotated_printer_sets4sub_zone

def bound_sub_zone(sub_zone, storage_orientation, wall_location, partial_individual, 
                   printer_sets4sub_zone, upbounds4sub_zone, unfold=False):
    rotated_sub_zone, rotated_upbounds4sub_zone, resulting_partial_individual, rotated_printer_sets4sub_zone = _transform_into_XY_axises(sub_zone, storage_orientation, upbounds4sub_zone, partial_individual, printer_sets4sub_zone)
    num_of_printer_sets, relative_rectangles4printer_sets, relative_partitioned_zones, boundary_against4partitioned_zones = _place_printer_sets_in_XY_axises(rotated_sub_zone, rotated_printer_sets4sub_zone)

    (relative_summed_plmts, relative_plmts_in_partitions, relative_RECTs_in_partitions), *results = _bound_sub_zone_in_XY_axises(resulting_partial_individual, rotated_upbounds4sub_zone, 
                                                                                                            rotated_printer_sets4sub_zone, relative_partitioned_zones, boundary_against4partitioned_zones)
    if storage_orientation:
        summed_plmts = {subject: (not parallel2x, nrows, ncols) for subject, (parallel2x, nrows, ncols) in relative_summed_plmts.items()}
    else:
        summed_plmts = relative_summed_plmts

    # relative_RECTs = chain.from_iterable(relative_RECTs_in_partitions)
    RECTs_in_partitions = [transform_RECTs(relative_RECTs_in_partition, storage_orientation, wall_location, sub_zone) 
                           for relative_RECTs_in_partition in relative_RECTs_in_partitions]
    plmts_in_partitions = [{subject: (not parallel2x if storage_orientation else parallel2x, nrows, ncols) for subject, (parallel2x, nrows, ncols) in relative_plmts_in_partition.items()}
                            for relative_plmts_in_partition in relative_plmts_in_partitions]
    partitioned_zones = transform_RECTs(relative_partitioned_zones, storage_orientation, wall_location, sub_zone)

    # relative_rectangles = unfold_RECTs_in_sub_zone(printer_sets4sub_zone, relative_RECTs, resulting_partial_individual)
    relative_rectangles= unfold_RECTs_in_partitions(relative_RECTs_in_partitions, relative_plmts_in_partitions, boundary_against4partitioned_zones)
    relative_rectangles['printer_sets'] = relative_rectangles4printer_sets
    rectangles = {comp: transform_components(rects, storage_orientation, wall_location, sub_zone) for comp, rects in relative_rectangles.items()}

    components = None
    if unfold: 
        relative_components = unfold_components_in_sub_zone(relative_rectangles, resulting_partial_individual)
        printers, paper_shredders = __unfold_a_partitioned_row_of_printer_sets(relative_rectangles4printer_sets)
        relative_components['printer'] = printers
        relative_components['paper_shredder'] = paper_shredders
        components = {comp: transform_components(rects, storage_orientation, wall_location, sub_zone) for comp, rects in relative_components.items()}
    return components, rectangles, (printer_sets4sub_zone[0], num_of_printer_sets), (summed_plmts, plmts_in_partitions, RECTs_in_partitions, partitioned_zones, boundary_against4partitioned_zones), *results