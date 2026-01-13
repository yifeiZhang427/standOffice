from collections import defaultdict
import math
from itertools import chain

from .bound_storage_plmts import *
from .bound_main_zone import __get_walls4main_zone, __sort_placement_by_walls

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from general.configs import storage, sizes
from general.utils import _calcu_occupied_length_for_subjects


def bound_storage(main_zones, desk_orientations4main_zones, boundary_against_in_Y_axis4main_zones, boundary_against4main_zones,
                  num_of_storage_in_axises4main_zones, num_of_printer_sets_in_axises4main_zones, relative_plmts4printer_sets_and_storage4main_zones,
                  sub_zones, storage_orientations4sub_zones, 
                  RECTs_list, indexes, upbounds,
                  num_of_persons, num_of_subjects_per_col4main_zones, total_num_of_islands4storage,
                  printer_sets4sub_zones, individual,
                  unfold=False,
                  inputs4global_layout=None,
                  inputs4local_layout=None, 
                  storage_opts=['locker', 'cabinet'], storage=storage, sizes=sizes,
                  priorities4walls={'down': 0, 'left': 1, 'right': 2, 'up': 3}):

    penalties_in_order_of_priority = {}
    storage_plmts = defaultdict(list)
    incremental_storages = {}

    if inputs4local_layout:
        required_storage = {comp.split('_')[-1][:-1]: num for comp, num in inputs4local_layout.items() if comp in ['big_lockers', 'high_cabinets']}
        storage = {comp: {_type: 1 for _type in types.keys() if _type in ['big', 'high']} for comp, types in storage.items()}
    else:
        magnification = {storage: inputs4global_layout[key] for storage, key in zip(storage_opts, ['CabinetMagnification', 'fileCabinetFm'])}
        required_storage = {comp: num_of_persons * multiplier for comp, multiplier in magnification.items()}
    
    _calcu_storage_sofar = lambda storage_plmts: {
        comp: sum(plmt[comp][0] * plmt[comp][1] for _, plmts in storage_plmts.items() for plmt in plmts if comp in plmt)
                for comp in storage_opts
    }

    priorities = ('two_col_islands', 'sub_zones', 'main_zones_walls_in_axises',
                #   'main_zones_walls', 
                  'main_zones_two_col_low_cabinets', 'mixed_cabinets_island')
    _get_storage_unit = lambda locker_opt, cabinet_opt, storage=storage: {
        'locker': storage['locker'][locker_opt],
        'cabinet': storage['cabinet'][cabinet_opt]
    }
    index4main_zones, index4sub_zones = indexes
    upbounds4main_zones, upbounds4sub_zones = upbounds
    for prior in priorities:
        storage_assigned_sofar = _calcu_storage_sofar(storage_plmts)

        penalties = []
        if prior == 'two_col_islands':
            if inputs4local_layout:
                storage_partition_below_two_col_islands = (None, None)
            else:
                _unit, _num = _get_storage_unit('small', 'low'), 2
                
                num4lockers = min(total_num_of_islands4storage, math.ceil(min(total_num_of_islands4storage * _num * _unit['locker'], required_storage['locker']) / (_num * _unit['locker'])))
                num4cabinets = total_num_of_islands4storage - num4lockers

                plmt = {comp: (num * _num, _unit[comp]) for comp, num in zip(storage_opts, [num4lockers, num4cabinets])}
                storage_plmts[prior].append(plmt)
                storage_partition_below_two_col_islands = (num4lockers*_num, num4cabinets*_num)

        elif prior == 'sub_zones':
            _unit = _get_storage_unit('big', 'high')

            k, delta = index4sub_zones
            for sub_zone, storage_orientation, printer_sets4sub_zone, (summed_plmts, plmts_in_partitions, *_), upbounds4sub_zone in zip(sub_zones, storage_orientations4sub_zones, printer_sets4sub_zones, RECTs_list, upbounds4sub_zones):
                prev_assigned_storage_sofar = _calcu_storage_sofar(storage_plmts)

                partial_individual = individual[k:k+delta]
                # half = int(delta/2)
                # plmt4lockers, plmt4cabinets = partial_individual[:half], partial_individual[half:] 

                # # plmts_in_partitions, *_ = RECTs_partitioned
                # _plmt4lockers = _sum_up('big_lockers', plmt4lockers, plmts_in_partitions)
                # _plmt4cabinets = _sum_up('high_cabinets', plmt4cabinets, plmts_in_partitions)
                # plmt = {comp: (nrows * ncols, _unit[comp]) for comp, (_, nrows, ncols) in zip(storage_opts, [_plmt4lockers, _plmt4cabinets])}

                plmt = {comp: (nrows * ncols, _unit[comp]) for comp, (_, nrows, ncols) in zip(storage_opts, [summed_plmts['big_lockers'], summed_plmts['high_cabinets']])}
                storage_plmts[prior].append(plmt)

                # penalty = bound_storage_plmts_in_sub_zone(sub_zone, storage_orientation, plmt4lockers, plmt4cabinets, RECTs_partitioned, comp_upbounds,
                #                                           _unit, prev_assigned_storage_sofar, required_storage)
                
                penalty = bound_storage_plmts_in_partitions(sub_zone, storage_orientation, upbounds4sub_zone, partial_individual, printer_sets4sub_zone, 
                                                                _unit, prev_assigned_storage_sofar, required_storage)
                
                penalties.append(penalty)
                k += delta
            penalties = {subject: [p[subject] for p in penalties] for subject in storage_opts}
        elif prior == 'main_zones_walls_in_axises':
            _unit = _get_storage_unit('big', 'high')

            gaps_of_plmts4walls_in_main_zones = []
            for main_zone, boundary_against_in_Y_axis4main_zone, boundary_against4main_zone,\
                num_of_storage_in_axises4main_zone, num_of_printer_sets_in_axises4main_zone, \
                relative_plmts4printer_sets_and_storage, upbounds4main_zone in zip(main_zones, boundary_against_in_Y_axis4main_zones, boundary_against4main_zones,
                                                                                   num_of_storage_in_axises4main_zones, num_of_printer_sets_in_axises4main_zones, 
                                                                                    relative_plmts4printer_sets_and_storage4main_zones, upbounds4main_zones):
                
                available_walls = __get_walls4main_zone(boundary_against_in_Y_axis4main_zone, boundary_against4main_zone)
                _available_walls_in_priority = __sort_placement_by_walls(available_walls, num_of_storage_in_axises4main_zone, num_of_printer_sets_in_axises4main_zone)
                _penalties_in_axises = []
                delta = 6
                # for (wall, shifted_zone4both), (*_, (relative_plmts_in_partitions_in_X_axis, _)) in relative_plmts4printer_sets_and_storage.items():
                #     prev_assigned_storage_sofar = _calcu_storage_sofar(storage_plmts)

                #     # num_of_storage_in_axis = num_of_storage_in_axises4main_zone[delta*j:delta*j + delta]
                #     # num_of_printer_sets_in_axis = num_of_printer_sets_in_axises4main_zone[j]
                #     _, num_of_printer_sets_in_axis, num_of_storage_in_axis = _available_walls_in_priority[wall]

                #     storage_orientation = True if wall in ['left', 'right'] else False
                #     if storage_orientation:
                #         num_of_storage_in_X_axis = [not value if j % 3 == 0 else value for j, value in enumerate(num_of_storage_in_axis)]
                #     else:
                #         num_of_storage_in_X_axis = num_of_storage_in_axis

                #     half = int(delta/2)
                #     plmt4lockers, plmt4cabinets = num_of_storage_in_X_axis[:3], num_of_storage_in_X_axis[3:]
                    
                #     _plmt4lockers = _sum_up('big_lockers', plmt4lockers, relative_plmts_in_partitions_in_X_axis)
                #     _plmt4cabinets = _sum_up('high_cabinets', plmt4cabinets, relative_plmts_in_partitions_in_X_axis)
                #     plmt = {comp: (nrows * ncols, _unit[comp]) for comp, (_, nrows, ncols) in zip(storage_opts, [_plmt4lockers, _plmt4cabinets])}
                #     storage_plmts[prior].append(plmt)

                #     printer_sets_in_X_axis = (1, num_of_printer_sets_in_axis)
                #     _upbounds4main_zone = upbounds4main_zone[f'in_{'Y' if wall in ['left', 'right'] else 'X'}_axis']
                #     penalty = bound_storage_plmts_in_partitions(shifted_zone4both, storage_orientation, _upbounds4main_zone, num_of_storage_in_axis, printer_sets_in_X_axis, 
                #                                                     _unit, prev_assigned_storage_sofar, required_storage)
                    
                #     _penalties_in_axises.append(penalty)
                # penalties += _penalties_in_axises

                _gaps_of_plmts4walls = {}
                _penalties4walls = []
                for (wall, shifted_zone4both, _, total_plmts4storage_in_X_axis, (maxY_in_X_axis, minY_in_X_axis)), plmts_partitioned_by_door in relative_plmts4printer_sets_and_storage.items():
                    _gaps_of_plmts4walls[wall] = (maxY_in_X_axis - minY_in_X_axis)
                    # *_, num_of_printer_sets_in_axis, num_of_storage_in_axis = _available_walls_in_priority[wall]
                    # storage_orientation = True if wall in ['left', 'right'] else False
                    # if storage_orientation:
                    #     num_of_storage_in_X_axis = [not value if j % 3 == 0 else value for j, value in enumerate(num_of_storage_in_axis)]
                    # else:
                    #     num_of_storage_in_X_axis = num_of_storage_in_axis
                    # printer_sets_in_X_axis = (True, num_of_printer_sets_in_axis)

                    # half = int(delta/2)
                    # plmt4lockers_in_X_axis, plmt4cabinets_in_X_axis = num_of_storage_in_X_axis[:3], num_of_storage_in_X_axis[3:]

                    prev_assigned_storage_sofar = _calcu_storage_sofar(storage_plmts)
                    # storage_plmts_partitioned_by_printer_sets = list(chain.from_iterable([storage_plmts_in_partitions for splitted_zone_by_door, _, partitioned_zone_by_printer_sets, boundary_against4partitioned_zones, _, storage_plmts_in_partitions, _ in plmts_partitioned_by_door]))
                    # _plmt4lockers = _sum_up('big_lockers', plmt4lockers_in_X_axis, storage_plmts_partitioned_by_printer_sets)
                    # _plmt4cabinets = _sum_up('high_cabinets', plmt4cabinets_in_X_axis, storage_plmts_partitioned_by_printer_sets)
                    # _plmt4wall = dict(zip(['big_lockers', 'high_cabinets'], [_plmt4lockers, _plmt4cabinets]))
                    _plmt4wall_in_X_axis = dict(zip(['big_lockers', 'high_cabinets'], total_plmts4storage_in_X_axis))
                    plmt = {comp.split('_')[-1][:-1]: (nrows * ncols, _unit[comp.split('_')[-1][:-1]]) for comp, (_, nrows, ncols) in _plmt4wall_in_X_axis.items()}
                    storage_plmts[prior].append(plmt)


                    partitioned_zones_by_printer_sets = list(chain.from_iterable([partitioned_zone_by_printer_sets for _, _, partitioned_zone_by_printer_sets, *_ in plmts_partitioned_by_door]))
                    # l, w = sizes['storage']
                    # Ys4storage_in_X_axis = {(comp, parallel2x): 0 if nrows * ncols == 0 else _calcu_occupied_length_for_subjects(comp, nrows, w, near_wall=True) if parallel2x else l * ncols 
                    #                         for comp, (parallel2x, nrows, ncols) in _plmt4wall.items()}
                    # maxY4storage_in_X_axis = max(Ys4storage_in_X_axis.values())
                    # _, w = sizes['printer_set']
                    # maxY4both = max(maxY4storage_in_X_axis, w if num_of_printer_sets_in_axis > 0 else 0)
                    # _partitioned_zones_by_printer_sets = [(origin, (X, maxY4both)) for origin, (X, _) in partitioned_zones_by_printer_sets]

                    boundary_against4partitioned_zones = list(chain.from_iterable([boundary_against4partitioned_zones for _, _, _, boundary_against4partitioned_zones, *_ in plmts_partitioned_by_door]))
                    _penalties4wall = bound_storage_plmts_for_wall_in_X_axis_partitioned_by_door_and_printer_sets(wall, _plmt4wall_in_X_axis,
                                                                                                                    partitioned_zones_by_printer_sets, boundary_against4partitioned_zones,
                                                                                                                    _unit, prev_assigned_storage_sofar, required_storage)
                    _penalties4walls.append(_penalties4wall)

                penalties += _penalties4walls
                gaps_of_plmts4walls_in_main_zones.append(_gaps_of_plmts4walls)

            penalties = {subject: [p[subject] for p in penalties] for subject in storage_opts}
        # elif prior == 'main_zones_walls':
        #     _unit = _get_storage_unit('big', 'high')
        #     l, w = sizes['storage']

        #     k, delta = index4main_zones
        #     for main_zone, desk_orientation, comp_upbounds, num_of_subjects_per_col in zip(main_zones, desk_orientations4main_zones, upbounds4main_zones, num_of_subjects_per_col4main_zones):
        #         *_, subject_near_wall, num_of_subjects_near_wall = individual[k:k+delta]

        #         prev_assigned_storage_sofar = _calcu_storage_sofar(storage_plmts)
        #         subject = 'locker' if subject_near_wall else 'cabinet'

        #         if 'high_storage' in num_of_subjects_per_col.keys():
        #             _ncols = num_of_subjects_per_col['high_storage']
        #         else:
        #             _ncols = num_of_subjects_per_col['cabinet']
        #         plmt = {subject: (num_of_subjects_near_wall * _ncols, _unit[subject])}
        #         storage_plmts[prior].append(plmt)

        #         origin, (X, Y) = main_zone
        #         _main_zone = (origin, (X, l * _ncols))
        #         penalty = bound_storage_plmts_for_subjects_near_wall_in_main_zone(_main_zone, desk_orientation, subject, num_of_subjects_near_wall, comp_upbounds,
        #                                                                           _unit[subject], required_storage[subject] - prev_assigned_storage_sofar[subject])
        #         penalties.append(penalty)
                
        #         k += delta
        elif prior == 'main_zones_two_col_low_cabinets' and not inputs4local_layout:
            _unit = {'cabinet': storage['cabinet']['low']}

            k, delta = index4main_zones
            for main_zone, comp_upbounds, num_of_subjects_per_col in zip(main_zones, upbounds4main_zones, num_of_subjects_per_col4main_zones):
                _, num_of_two_col_low_cabinets, _ = individual[k:k+delta]

                prev_assigned_storage_sofar = _calcu_storage_sofar(storage_plmts)
                plmt = {'cabinet': (num_of_two_col_low_cabinets * 2 * num_of_subjects_per_col['cabinet'], _unit['cabinet'])}
                storage_plmts[prior].append(plmt)

                penalty = bound_storage_plmts_for_two_col_cabinets_in_main_zone(comp_upbounds['low_cabinets'][0], num_of_two_col_low_cabinets,
                                                                                num_of_subjects_per_col['cabinet'], _unit['cabinet'], required_storage['cabinet'] - prev_assigned_storage_sofar['cabinet'])
                penalties.append(penalty)

                k += delta
        elif prior == 'mixed_cabinets_island' and not inputs4local_layout:
            _unit = {'cabinet': storage['cabinet']['low']}

            k, delta = index4main_zones
            for main_zone, comp_upbounds, num_of_subjects_per_col in zip(main_zones, upbounds4main_zones, num_of_subjects_per_col4main_zones):
                _, _, has_mixed_cabinets_island = individual[k:k+delta]

                prev_assigned_storage_sofar = _calcu_storage_sofar(storage_plmts)
                if has_mixed_cabinets_island:                         
                    plmt = {'cabinet': (1 * num_of_subjects_per_col['mixed_cabinet'], _unit['cabinet'])}
                    storage_plmts[prior].append(plmt)

                penalty = bound_storage_plmts_for_mixed_island_in_main_zone(has_mixed_cabinets_island, required_storage['cabinet'] - prev_assigned_storage_sofar['cabinet'])
                penalties.append(penalty)

                k += delta

        penalties_in_order_of_priority[prior] = penalties
        incremental_storages[prior] = {subject: _calcu_storage_sofar(storage_plmts)[subject] - storage_assigned_sofar[subject] for subject in storage_opts}


    storage_assigned_sofar = _calcu_storage_sofar(storage_plmts)
    return gaps_of_plmts4walls_in_main_zones, storage_partition_below_two_col_islands, \
           penalties_in_order_of_priority, storage_assigned_sofar, required_storage, \
           priorities[1:], storage_plmts, incremental_storages

