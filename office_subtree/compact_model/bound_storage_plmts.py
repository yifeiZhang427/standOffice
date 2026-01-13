from itertools import product
from copy import deepcopy
import random

from .find_a_sample_storage_plmt import find_a_compact_plmt4subjects_to_fill_storage, find_a_compact_plmt4two_col_cabinets_to_fill_storage

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from general.configs import spacing, sizes
from general.utils import _calcu_nrows4subjects, _calcu_occupied_length_for_subjects, calcu_max_matrix_within_zone4subjects
from compact_model.bound_sub_model import _transform_into_XY_axises, _place_printer_sets_in_XY_axises, place_storage_for_each_plmt_comb_within_zone


_penalty_func = lambda penalty, eps=10**10: penalty if penalty == 0 else eps

_stepwise_penalty_func = lambda stepNo, curr, opt, dimensions=3, eps=10**20: \
    10**(10 * (dimensions - stepNo)) * abs(curr - opt)


# eps = 10**10

def _get_optimal_parallel2x4subjects(sub_zone, subject, upbounds_specific2parallel2xs,
                                     subject_unit, storage_to_fill):
    parallel2x_results = {parallel2x: find_a_compact_plmt4subjects_to_fill_storage(sub_zone, subject, parallel2x, upbounds_specific2parallel2xs,
                                                                                    subject_unit, storage_to_fill) for parallel2x in [False, True]}
    optimal_parallel2x = True
    if parallel2x_results[False][0] * parallel2x_results[False][1] >= parallel2x_results[True][0] * parallel2x_results[True][1]:
        optimal_parallel2x = False
    return optimal_parallel2x, parallel2x_results[optimal_parallel2x]

def _get_penalties_by_priority_for_unexpected_plmts(curr_plmt, optimal_plmt):
    # penalties = [_penalty_func(abs(curr - opt)) for curr, opt in zip(curr_plmt, optimal_plmt)]
    penalties = [_stepwise_penalty_func(i, curr, opt) for i, (curr, opt) in enumerate(zip(curr_plmt, optimal_plmt))]
    
    # gaps = [abs(curr - opt) for curr, opt in zip(curr_plmt, optimal_plmt)]
    # gap4parallel2x, gap4nrows, gap4ncols = gaps
    # # penalties = [gap4parallel2x * (1 if gap4nrows + gap4ncols > 0 else 0), gap4nrows**2, gap4ncols**2]
    # # penalties = [eps * p for p in penalties]
    # penalties = [gap4parallel2x * (1 if gap4nrows + gap4ncols > 0 else 0), gap4nrows, gap4ncols]
    # penalties = [_penalty_func(p) for p in penalties]
    return penalties


def bound_storage_plmts_in_sub_zone(sub_zone, storage_orientation, plmt4lockers, plmt4cabinets, RECTs, comp_upbounds,
                                    _unit, prev_assigned_storage_sofar, required_storage,
                                    spacing=spacing):
    penalties_by_priority = {}

    upbounds_specific2parallel2xs = {comp: comp_upbounds[comp][parallel2x] 
                                    for comp, (parallel2x, *_) in zip(['big_lockers', 'high_cabinets'], [plmt4lockers, plmt4cabinets])}


    optimal_plmt4lockers = _get_optimal_parallel2x4subjects(sub_zone, 'locker', upbounds_specific2parallel2xs,
                                                            _unit['locker'], required_storage['locker'] - prev_assigned_storage_sofar['locker'])
    penalties_by_priority['locker'] = _get_penalties_by_priority_for_unexpected_plmts(plmt4lockers, optimal_plmt4lockers)

    _, nrows, ncols = plmt4lockers
    if not (nrows and ncols):
        remained_sub_zone = sub_zone
    else:
        _, (X, Y) = sub_zone
        _, RECT4lockers = RECTs[0]
        lX, lY = RECT4lockers
        _spacing = spacing['locker']['against_self']['longside']
        remained_sub_zone = (X - lX - _spacing, Y)  if not storage_orientation else (X, Y - lY - _spacing)
        remained_sub_zone = ('space_holder', remained_sub_zone)          
    optimal_plmt4cabinets = _get_optimal_parallel2x4subjects(remained_sub_zone, 'cabinet', upbounds_specific2parallel2xs,
                                                             _unit['cabinet'], required_storage['cabinet'] - prev_assigned_storage_sofar['cabinet'])              
    penalties_by_priority['cabinet'] = _get_penalties_by_priority_for_unexpected_plmts(plmt4cabinets, optimal_plmt4cabinets)
    return penalties_by_priority


def __find_min_nrows(_max_nrows, _ncols, 
                     _subject, _unit, _remained_storage):
    min_nrows = None
    for nrows in range(_max_nrows + 1):
        min_nrows = nrows

        placed_storage = _ncols * nrows * _unit[_subject]
        if placed_storage >= _remained_storage[_subject]:
            break
                
    return min_nrows


def __find_min_ncols(_max_cols, _nrows,
                    _subject, _unit, _remained_storage):
    min_ncols = __find_min_nrows(_max_cols, _nrows, _subject, _unit, _remained_storage)
    return min_ncols


def _find_the_most_compact_plmt_with_minY(possible_plmt_in_general, _unit, _remained_storage, zoneY, sizes=sizes):
    compact_plmt = {}
    # maxY = None

    l, w = sizes['storage']
    for subject, (parallel2x, _nrows, _ncols) in possible_plmt_in_general.items():
        _subject = subject.split('_')[-1][:-1]
        if parallel2x:
            _max_nrows = _calcu_nrows4subjects(subject, w, zoneY, near_wall=True)
            # plmts = [nrows for nrows in range(_max_nrows + 1) if _ncols * nrows > 0 and  _ncols * nrows * _unit[_subject] <= _remained_storage[_subject]]
            # if plmts:
                # min_nrows = plmts[-1]
            min_nrows = __find_min_nrows(_max_nrows, _ncols, _subject, _unit, _remained_storage)
            if min_nrows > 0:
                Y = _calcu_occupied_length_for_subjects(subject, min_nrows, w)
                compact_plmt[subject] = ((parallel2x, min_nrows, _ncols), min_nrows * _ncols * _unit[_subject], 0 if _ncols == 0 else Y)
                # if maxY is None or Y > maxY:
                #     maxY = Y
            else:
                compact_plmt[subject] = ((parallel2x, 0, 0), 0, 0)
        else:
            _max_ncols = int(zoneY / l)
            # plmts = [ncols for ncols in range(_max_ncols + 1) if _nrows * ncols > 0 and _nrows * ncols * _unit[_subject] <= _remained_storage[_subject]]
            # if plmts:
            #     min_ncols = plmts[-1]
            min_ncols = __find_min_ncols(_max_ncols, _nrows, _subject, _unit, _remained_storage)
            if min_ncols > 0:
                Y = min_ncols * l
                compact_plmt[subject] = ((parallel2x, _nrows, min_ncols), _nrows * min_ncols * _unit[_subject], 0 if _nrows == 0 else Y)
                # if maxY is None or Y > maxY:
                #     maxY = Y
            else:
                compact_plmt[subject] = ((parallel2x, 0, 0), 0, 0)

    # return (compact_plmt, maxY)
    return compact_plmt


def _get_optimal_plmt_result(all_possible_plmt_results, _remained_storage, each_plmt_comb,
                            subjects=['big_lockers', 'high_cabinets'],
                            within_main_zone=True):
    _get_subject = lambda subject: subject.split('_')[-1][:-1]

    # storage_satisfied = {subject: any(plmt[subject][-1] >= _remained_storage[_get_subject(subject)] for plmt, _ in all_possible_plmt_results)
    #                      for subject in subjects}

    __get_storage_satisfiability = lambda all_plmt_results, _remained_storage, subjects=subjects: \
                                        (True, True) if [plmt for plmt in all_plmt_results if all(plmt[subject][1] >= _remained_storage[_get_subject(subject)] for subject in subjects)] else \
                                        (True, False) if [plmt for plmt in all_plmt_results if plmt['big_lockers'][1] >= _remained_storage['locker']] else \
                                        (False, True) if [plmt for plmt in all_plmt_results if plmt['high_cabinets'][1] >= _remained_storage['cabinet']] else \
                                        (False, False)
    storage_satisfiability = dict(zip(subjects, __get_storage_satisfiability(all_possible_plmt_results, _remained_storage)))

    __keys_to_get_preferred_plmt = lambda plmt_result, within_main_zone=within_main_zone: (max(plmt_result['big_lockers'][2], plmt_result['high_cabinets'][2]),
                                                                                            abs(plmt_result['big_lockers'][2] - plmt_result['high_cabinets'][2])) if within_main_zone else \
                                                                                            (plmt_result['big_lockers'][2], plmt_result['high_cabinets'][2])
                                                                                        #    -max(plmt_result['big_lockers'][2], plmt_result['high_cabinets'][2]),
                                                                                        #    - min(plmt_result['big_lockers'][2], plmt_result['high_cabinets'][2])
    all_plmt_results = deepcopy(all_possible_plmt_results)
    if all(storage_satisfiability[subject] for subject in subjects):
        reduced_plmt_results = [plmt for plmt in all_plmt_results if all(plmt[subject][1] >= _remained_storage[_get_subject(subject)] for subject in subjects)]
        
        # reduced_plmt_results = deepcopy(all_plmt_results)
        # for subject in subjects:
        #     reduced_plmt_results = [(plmt, maxY) for plmt, maxY in reduced_plmt_results if plmt[subject][-1] >= _remained_storage[_get_subject(subject)]]

        # sorted_results = sorted(reduced_plmt_results, key=lambda plmt_result: (plmt_result['big_lockers'][1], plmt_result['high_cabinets'][1], 
        #                                                                        *__keys_to_get_preferred_plmt(plmt_result)))
        
        sorted_results = sorted(reduced_plmt_results, key=lambda plmt_result: (*__keys_to_get_preferred_plmt(plmt_result),
                                                                                plmt_result['big_lockers'][1], plmt_result['high_cabinets'][1]))
    elif storage_satisfiability['big_lockers']:
        reduced_plmt_results = [plmt for plmt in all_plmt_results if plmt['big_lockers'][1] >= _remained_storage['locker']]
        # sorted_results = sorted(reduced_plmt_results, key=lambda plmt_result: (plmt_result['big_lockers'][1], -plmt_result['high_cabinets'][1],
        #                                                                         *__keys_to_get_preferred_plmt(plmt_result)))

        sorted_results = sorted(reduced_plmt_results, key=lambda plmt_result: (*__keys_to_get_preferred_plmt(plmt_result), 
                                                                                plmt_result['big_lockers'][1], -plmt_result['high_cabinets'][1]))
    elif storage_satisfiability['high_cabinets']:
        reduced_plmt_results = [plmt for plmt in all_plmt_results if plmt['high_cabinets'][1] >= _remained_storage['cabinet']]
        # sorted_results = sorted(reduced_plmt_results, key=lambda plmt_result: (-plmt_result['big_lockers'][1], plmt_result['high_cabinets'][1],
        #                                                                         *__keys_to_get_preferred_plmt(plmt_result)))

        sorted_results = sorted(reduced_plmt_results, key=lambda plmt_result: (*__keys_to_get_preferred_plmt(plmt_result),
                                                                                -plmt_result['big_lockers'][1], plmt_result['high_cabinets'][1]))
    else:
        sorted_results = sorted(all_plmt_results, key=lambda plmt_result: (-plmt_result['big_lockers'][1], -plmt_result['high_cabinets'][1],
                                                                            *__keys_to_get_preferred_plmt(plmt_result)))

        # sorted_results = sorted(all_plmt_results, key=lambda plmt_result: (*__keys_to_get_preferred_plmt(plmt_result),
        #                                                                     -plmt_result['big_lockers'][1], -plmt_result['high_cabinets'][1]))

    
    if sorted_results:
        optimal_plmt = sorted_results[0]
    else:
        optimal_plmt = {subject: ((parallel2x, 0, 0), 0, 0) for subject, parallel2x in each_plmt_comb.items()}
    return optimal_plmt
    

def _seperate_storage_plmts_in_partitioned_zones(picked_plmts4partitioned_zones, plmts_with_maxX4big_lockers, each_plmt_comb):
    storage_seperation_combs = []
    
    def __seperate_storage_plmts(i, plmts_with_maxX4big_lockers):
        seperated_storage_plmt = {}
        for subject, parallel2x in each_plmt_comb.items():
            assigned_plmts = plmts_with_maxX4big_lockers[:i] if subject == 'big_lockers' else plmts_with_maxX4big_lockers[i+1:]

            if parallel2x:
                summed_ncols = sum(plmt[subject][2] for plmt in assigned_plmts)
                seperated_storage_plmt[subject] = (parallel2x, None, summed_ncols)
            else:
                summed_nrows = sum(plmt[subject][1] for plmt in assigned_plmts)
                seperated_storage_plmt[subject] = (parallel2x, summed_nrows, None)
        return seperated_storage_plmt

    def __combine(picked_plmt, seperated_storage_plmt):
        combined_storage_plmt = {}
        for subject, (parallel2x, nrows, ncols) in picked_plmt.items():
            if parallel2x:
                combined_storage_plmt[subject] = (parallel2x, nrows, ncols + seperated_storage_plmt[subject][2])
            else:
                combined_storage_plmt[subject] = (parallel2x, nrows + seperated_storage_plmt[subject][1], ncols)
        return combined_storage_plmt

    for i, picked_plmts in enumerate(picked_plmts4partitioned_zones):
        seperated_storage_plmt = __seperate_storage_plmts(i, plmts_with_maxX4big_lockers)

        storage_seperation_combs += [__combine(picked_plmt, seperated_storage_plmt) for picked_plmt in picked_plmts]
    return storage_seperation_combs


def check_each_plmt_comb_in_partitioned_zones(each_plmt_comb, _unit, _remained_storage,
                                              relative_partitioned_zones, boundary_against4partitioned_zones,
                                              within_main_zone=True):
    picked_plmts4partitioned_zones = []
    plmts_with_maxX4big_lockers = []
    for i, (zone, _boundary_against) in enumerate(zip(relative_partitioned_zones, boundary_against4partitioned_zones)):
        plmt_with_maxX4big_lockers = place_storage_for_each_plmt_comb_within_zone(each_plmt_comb, zone, _boundary_against,
                                                                                partial_plmt=None)
        parallel2x4big_lockers = each_plmt_comb['big_lockers']

        if 'big_lockers' in plmt_with_maxX4big_lockers.keys():
            max_plmt4big_lockers = plmt_with_maxX4big_lockers['big_lockers']
        else:
            max_plmt4big_lockers = (parallel2x4big_lockers, None, 0) if parallel2x4big_lockers else (parallel2x4big_lockers, 0, None)

        # _sample_nums = lambda max_num, k=4: sorted(set([0] + list(random.sample(range(1, max_num), min(max_num, int(max_num / k)))) + [max_num]))
        _sample_nums = lambda max_num, k=3: [max_num] if max_num == 0 else \
                                            sorted(set(list(random.sample(range(0, max_num + 1, max(1, int(max_num / k))), min(max_num, k))) + [0, max_num]))
        if parallel2x4big_lockers:
            *_, max_ncols = max_plmt4big_lockers
            picked_plmts4zone = [place_storage_for_each_plmt_comb_within_zone(each_plmt_comb, zone, _boundary_against,
                                                                                        partial_plmt={'big_lockers': (parallel2x4big_lockers, None, num)})
                                                # for num in range(max_ncols + 1)]
                                                for num in _sample_nums(max_ncols)]
        else:
            _, max_nrows, _ = max_plmt4big_lockers
            picked_plmts4zone = [place_storage_for_each_plmt_comb_within_zone(each_plmt_comb, zone, _boundary_against,
                                                                                        partial_plmt={'big_lockers': (parallel2x4big_lockers, num, None)})
                                                # for num in range(max_nrows + 1)]
                                                for num in _sample_nums(max_nrows)]
        picked_plmts4partitioned_zones += [picked_plmts4zone]
        plmts_with_maxX4big_lockers += [plmt_with_maxX4big_lockers]

    storage_seperation_combs = _seperate_storage_plmts_in_partitioned_zones(picked_plmts4partitioned_zones, plmts_with_maxX4big_lockers, each_plmt_comb)

    _, (zoneX, zoneY) = relative_partitioned_zones[0]
    all_possible_plmt_results = []
    for storage_seperation_comb in storage_seperation_combs:
        if within_main_zone:
            compact_plmt_result = _find_the_most_compact_plmt_with_minY(storage_seperation_comb, _unit, _remained_storage, zoneY)
            if all(compact_plmt_result):
                all_possible_plmt_results.append(compact_plmt_result)
        else:
            fixed_plmt_result = {}
            for subject, (parallel2x, nrows, ncols) in storage_seperation_comb.items():
                _subject = subject.split('_')[-1][:-1]
                if parallel2x:
                    max_nrows, _ = calcu_max_matrix_within_zone4subjects(subject, parallel2x, (zoneX, zoneY), near_wall=True)
                    if _remained_storage[_subject] <= 0:
                        ncols = 0
                    fixed_plmt_result[subject] = ((parallel2x, max_nrows, ncols), max_nrows * ncols * _unit[_subject], zoneY if max_nrows * ncols > 0 else 0)
                else:
                    _, max_ncols = calcu_max_matrix_within_zone4subjects(subject, parallel2x, (zoneX, zoneY), near_wall=True)
                    if _remained_storage[_subject] <= 0:
                        nrows = 0
                    fixed_plmt_result[subject] = ((parallel2x, nrows, max_ncols), nrows * max_ncols * _unit[subject.split('_')[-1][:-1]], zoneY if nrows * max_ncols > 0 else 0)
            all_possible_plmt_results.append(fixed_plmt_result)

    optimal_plmt_result = _get_optimal_plmt_result(all_possible_plmt_results, _remained_storage, each_plmt_comb, within_main_zone=within_main_zone)
    return optimal_plmt_result


def bound_storage_plmts_in_partitions(sub_zone, storage_orientation, upbounds4sub_zone, partial_individual, printer_sets4sub_zone, 
                                      _unit, prev_assigned_storage_sofar, required_storage,
                                      subjects=['big_lockers', 'high_cabinets'],
                                      within_main_zone=False):
    remained_storage = {subject: required_storage[subject] - prev_assigned_storage_sofar[subject] for subject in ['locker', 'cabinet']}

    rotated_sub_zone, rotated_upbounds4sub_zone, rotated_partial_individual, rotated_printer_sets4sub_zone = _transform_into_XY_axises(sub_zone, storage_orientation, upbounds4sub_zone, partial_individual, printer_sets4sub_zone)
    _, relative_rectangles4printer_sets, relative_partitioned_zones, boundary_against4partitioned_zones = _place_printer_sets_in_XY_axises(rotated_sub_zone, rotated_printer_sets4sub_zone)
    relative_plmts4subjects = {subject: rotated_partial_individual[3*i:3*i+3] for i, subject in enumerate(subjects)}
    # if storage_orientation:
    #     relative_plmts4subjects = {subject: (not parallel2x, nrows, ncols) for subject, (parallel2x, nrows, ncols) in resulting_plmts4subjects.items()}
    # else:
    #     relative_plmts4subjects = resulting_plmts4subjects

    relative_parallel2xs = [False, True]
    plmt_combinations = [dict(zip(subjects, plmts)) for plmts in product(relative_parallel2xs, repeat=2)]

    relative_results = []
    for each_plmt_comb in plmt_combinations:
        _remained_storage = deepcopy(remained_storage)
        # plmts_in_partitions, _remained_storage = check_each_plmt_comb_in_partitioned_zones(each_plmt_comb, _unit, _remained_storage,
        #                                                                                     relative_partitioned_zones, boundary_against4partitioned_zones)
        # summed_plmts = {subject: (value, sum([plmt[subject][1] if subject in plmt.keys() else 0 for plmt in plmts_in_partitions ]), 
        #                           plmts_in_partitions[0][subject][-1] if subject in plmts_in_partitions[0].keys() else 0) 
        #                 for subject, value in each_plmt_comb.items()}
        # relative_results.append((summed_plmts, _remained_storage))

        _optimal_plmt = check_each_plmt_comb_in_partitioned_zones(each_plmt_comb, _unit, _remained_storage,
                                                                        relative_partitioned_zones, boundary_against4partitioned_zones,
                                                                        within_main_zone=within_main_zone)
        relative_results.append(_optimal_plmt)

    # if storage_orientation:
    #     # results = [({subject: (not parallel2x, *matrix) for subject, (parallel2x, *matrix) in summed_plmts.items()}, _remained_storage)
    #     #            for summed_plmts, _remained_storage in relative_results]
    #     results = [({subject: ((not parallel2x, nrows, ncols), placed_storage) for subject, ((parallel2x, nrows, ncols), placed_storage) in _optimal_plmt.items()}, minY) for _optimal_plmt, minY in relative_results]
    # else:
    #     results = relative_results
    
    # _results = [(summed_plmts, {subject: 0 if value < 0 else value for subject, value in _remained_storage.items()})
    #             for summed_plmts, _remained_storage in results]
    # sorted_results = sorted(_results, key=lambda item: (item[1]['locker'], item[1]['cabinet']))

    # _get_placed_storage = lambda subject, optimal_plmt: optimal_plmt[subject][-1] if optimal_plmt and subject in optimal_plmt.keys() else 0
    # sorted_results = sorted(results, key=lambda plmt_result: (- _get_placed_storage('big_lockers', plmt_result[0]),
    #                                                             - _get_placed_storage('high_cabinets', plmt_result[0]),     
    #                                                             plmt_result[1]))
    # _optimal_plmt_comb, _ = sorted_results[0]
    # optimal_plmt_comb = {subject: plmt for subject, (plmt, _) in _optimal_plmt_comb.items()}

    curr_relative_plmt_comb = {subject: parallel2x for subject, (parallel2x, *_) in relative_plmts4subjects.items()}
    _optimal_plmt_comb = _get_optimal_plmt_result(relative_results, remained_storage, curr_relative_plmt_comb, within_main_zone=within_main_zone)
    optimal_plmt_comb = {subject: plmt for subject, (plmt, *_) in _optimal_plmt_comb.items()}

    penalties_by_priority = {subject.split('_')[-1][:-1] if '_' in subject else subject: _get_penalties_by_priority_for_unexpected_plmts(curr_plmt4subject, optimal_plmt_comb[subject]) 
                             for subject, curr_plmt4subject in relative_plmts4subjects.items()}
    return penalties_by_priority


def _check_all_possible_storage_plmts_for_wall_in_X_axis_partitioned_by_door_and_printer_sets(wall, partitioned_zones, boundary_against4partitioned_zones,
                                                                                                _unit, prev_assigned_storage_sofar, required_storage,
                                                                                                subjects=['big_lockers', 'high_cabinets']):
    remained_storage = {subject: required_storage[subject] - prev_assigned_storage_sofar[subject] for subject in ['locker', 'cabinet']}


    parallel2xs = [True, False]
    plmt_combinations = [dict(zip(subjects, plmts)) for plmts in product(parallel2xs, repeat=2)]

    relative_results = []
    for each_plmt_comb in plmt_combinations:
        _remained_storage = deepcopy(remained_storage)
        _optimal_plmt = check_each_plmt_comb_in_partitioned_zones(each_plmt_comb, _unit, _remained_storage,
                                                                        partitioned_zones, boundary_against4partitioned_zones)
        # summed_plmts = {subject: (value, sum([plmt[subject][1] if subject in plmt.keys() else 0 for plmt in plmts_in_partitions ]), 
        #                           plmts_in_partitions[0][subject][-1] if subject in plmts_in_partitions[0].keys() else 0) 
        #                 for subject, value in each_plmt_comb.items()}

        # optimal_plmt = {subject: plmt for subject, (plmt, _) in _optimal_plmt.items()}
        # # _get_subject = lambda _subject: 'big_' if _subject == 'locker' else 'high_' + _subject + 's'
        # # _remained_storage = {_subject: value - _optimal_plmt[_get_subject(_subject)][-1] if _get_subject(_subject) in _optimal_plmt.keys() else 0 for _subject, value in _remained_storage.items()}
        # placed_storage = {subject: storage for subject, (_, storage) in _optimal_plmt.items()}
        # relative_results.append((optimal_plmt, placed_storage, minY))
        relative_results.append(_optimal_plmt)

    return relative_results

def bound_storage_plmts_for_wall_in_X_axis_partitioned_by_door_and_printer_sets(wall, plmt4wall_in_X_axis,
                                                                                partitioned_zones, boundary_against4partitioned_zones,
                                                                                _unit, prev_assigned_storage_sofar, required_storage):
    all_possible_relative_results = _check_all_possible_storage_plmts_for_wall_in_X_axis_partitioned_by_door_and_printer_sets(wall, partitioned_zones, boundary_against4partitioned_zones,
                                                                                                                                _unit, prev_assigned_storage_sofar, required_storage)

    # # _results = [(summed_plmts, {subject: 0 if value < 0 else value for subject, value in _remained_storage.items()})
    # #             for summed_plmts, _remained_storage in all_possible_relative_results]
    # # sorted_results = sorted(_results, key=lambda item: (item[1]['locker'], item[1]['cabinet']))
    # # _get_value_to_compare = lambda parallel2x, nrows, ncols: ncols if parallel2x else nrows
    # # sorted_results = sorted(all_possible_relative_results, key=lambda result: [abs(result[1]['locker']), 
    # #                                                                             _get_value_to_compare(*result[0]['big_lockers']),
    # #                                                                             abs(result[1]['cabinet']), 
    # #                                                                             _get_value_to_compare(*result[0]['high_cabinets'])])

    # _get_placed_storage = lambda subject, optimal_plmt: optimal_plmt[subject][-1] if optimal_plmt and subject in optimal_plmt.keys() else 0
    # sorted_results = sorted(all_possible_relative_results, key=lambda plmt_result: (- _get_placed_storage('big_lockers', plmt_result[0]),
                                                                                   
    #                                                                                 plmt_result[1],
    #                                                                                  - _get_placed_storage('high_cabinets', plmt_result[0])),
    #                                                                                 )
    
    # _optimal_plmt_comb, _ = sorted_results[0]
    # optimal_plmt_comb = {subject: plmt for subject, (plmt, _) in _optimal_plmt_comb.items()}

    remained_storage = {subject: required_storage[subject] - prev_assigned_storage_sofar[subject] for subject in ['locker', 'cabinet']}
    curr_plmt_comb = {subject: parallel2x for subject, (parallel2x, *_) in plmt4wall_in_X_axis.items()}
    _optimal_plmt_comb = _get_optimal_plmt_result(all_possible_relative_results, remained_storage, curr_plmt_comb)
    optimal_plmt_comb = {subject: plmt for subject, (plmt, *_) in _optimal_plmt_comb.items()}

    penalties_by_priority = {subject.split('_')[-1][:-1] if '_' in subject else subject: 
                             _get_penalties_by_priority_for_unexpected_plmts(curr_plmt4subject, optimal_plmt_comb[subject]) 
                             for subject, curr_plmt4subject in plmt4wall_in_X_axis.items()}
    return penalties_by_priority



def bound_storage_plmts_for_subjects_near_wall_in_main_zone(main_zone, desk_orientation, subject, num_of_subjects, comp_upbounds,
                                                            subject_unit, storage_to_fill):
    penalty4subject, penalty4num = 0, 0
    if storage_to_fill <= 0:
        penalty4subject, penalty4num  = (1, num_of_subjects)
    else:
        min_num, _ = find_a_compact_plmt4subjects_to_fill_storage(main_zone, subject, desk_orientation, comp_upbounds,
                                                                  subject_unit, storage_to_fill)
        penalty4num = abs(min_num - num_of_subjects) 
    penalties_by_priority = (penalty4subject, penalty4num)
    return [_penalty_func(p) for p in penalties_by_priority]

    
def bound_storage_plmts_for_two_col_cabinets_in_main_zone(cabinet_upbound, num_of_two_col_cabinets,
                                                          num_of_cabinets_per_col, cabinet_unit, storage_to_fill):
   min_num = find_a_compact_plmt4two_col_cabinets_to_fill_storage(cabinet_upbound, num_of_cabinets_per_col, cabinet_unit, storage_to_fill)
#    return _penalty_func(abs(num_of_two_col_cabinets - min_num))
   return _stepwise_penalty_func(1, num_of_cabinets_per_col, min_num)
#    return _penalty_func(eps * (num_of_two_col_cabinets - min_num)**2)
   

def bound_storage_plmts_for_mixed_island_in_main_zone(has_mixed_cabinets_island, storage_to_fill):
    opt_num = 0 if storage_to_fill <=0 else 1
    # return _penalty_func(has_mixed_cabinets_island - opt_num)
    return _stepwise_penalty_func(1, has_mixed_cabinets_island, opt_num)
    # return _penalty_func(eps *(has_mixed_cabinets_island - opt_num))


