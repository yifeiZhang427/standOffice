from itertools import chain
from collections import defaultdict

from .model import bound

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from general.configs import storage


def extract_high_storage(storage_plmts, storage=storage):
    assigned_storage = defaultdict(list)

    for prior, plmts in storage_plmts.items():
        if prior not in ['main_zones_walls_in_axises', 'sub_zones']: continue

        for plmt in plmts:
            for subject, (num, unit) in plmt.items():
                # if num == 0: continue
                # prefix = [key for key, _unit in storage[subject].items() if _unit == unit][0]
                # assigned_storage[f'{prefix}_{subject}s'].append(num)

                prefix = 'big' if subject == 'locker' else 'high'
                assigned_storage[f'{prefix}_{subject}s'].append(num)
    assigned_storage_in_total = {subject: sum(values) for subject, values in assigned_storage.items()}
    return assigned_storage_in_total
            

def bound_in_nums_outputed(outputs, inputs, priorities4bounding=dict(zip(['islandSpaceing',
                                                                          'accompanyment_seats',
                                                                          'persons',
                                                                          
                                                                          'small_lockers', 'low_cabinets', 
                                                                          
                                                                          'printer_sets',
                                                                          'big_lockers', 'high_cabinets'
                                                                          ], range(8)))):
    boundings = {key: 1 if key not in outputs.keys() else abs(outputs[key] - num)
                    for key, num in sorted(inputs.items(), key=lambda item: priorities4bounding[item[0]])}
    return boundings


def get_outputs(num_of_printer_sets_near_walls4main_zones, num_of_printer_sets_near_walls4sub_zones,
                assigned_num_of_accompaniment_seats_list,
                total_num_of_small_lockers, total_num_of_low_cabinets,
                high_storage_plmts,
                num_of_persons):
    outputs = {
        'printer_sets':sum(chain.from_iterable(num_of_printer_sets_near_walls4main_zone.values() for num_of_printer_sets_near_walls4main_zone in num_of_printer_sets_near_walls4main_zones)) \
                        + sum(num for _, num in num_of_printer_sets_near_walls4sub_zones), 
        'accompanyment_seats': sum(assigned_num_of_accompaniment_seats_list),
        'persons': num_of_persons,
        'small_lockers': total_num_of_small_lockers,
        'low_cabinets': total_num_of_low_cabinets
    }
    assigned_furnitures = extract_high_storage(high_storage_plmts)
    outputs = {**outputs, **assigned_furnitures}
    return outputs


def _evaluate_local_layout(main_door, boundary, upbounds, main_zones, desk_orientations4main_zones, passageway_locations4main_zones, 
                            walls4main_zones, boundary_against_in_Y_axis4main_zones, boundary_against4main_zones, connect_func,
                            sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, individual,
                            unfold=False, inputs4local_layout=None):
    total_num_of_low_cabinets, total_num_of_small_lockers, \
    with_main_zones_reflected, penalty4island_connectivity, (aggregated_components_dict, aggregated_rectangles_dict, RECTs_dict,
    # islands, printer_sets, _islands2printer_sets, _grouped_islands,
    gaps_of_plmts4walls_in_main_zones, num_of_printer_sets_near_walls4sub_zones, num_of_printer_sets_near_walls4main_zones, 
    total_overbounds_of_parallel2x4storage, total_overbounds_of_storage, total_overbounds_of_printer_sets,
    assigned_num_of_accompaniment_seats_list, total_insufficiency_of_accompaniment_seats, total_bound_in_accompaniment_seats_without_islands,
    num_of_islands4storage_list, overbounds_within_main_zones, overbounds_within_sub_zones, total_overbounds_of_high_cabinets_near_wall, num_of_persons, 
    indexes), (penalties_in_order_of_priority, storage_assigned_sofar, required_storage, _priorities, high_storage_plmts, incremental_storages) = \
    bound(main_door, boundary, upbounds, main_zones, desk_orientations4main_zones, passageway_locations4main_zones, 
          walls4main_zones, boundary_against_in_Y_axis4main_zones, boundary_against4main_zones, connect_func,
              sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, individual,
              unfold=unfold,
              inputs4local_layout=inputs4local_layout)
    
    outputs = get_outputs(num_of_printer_sets_near_walls4main_zones, num_of_printer_sets_near_walls4sub_zones,
                            assigned_num_of_accompaniment_seats_list,
                            total_num_of_small_lockers, total_num_of_low_cabinets,
                            high_storage_plmts,
                            num_of_persons)

    _inputs4local_layout = {key: value for key, value in inputs4local_layout.items() if key not in ['width', 'height', 'islandSpaceing']}
    boundings = bound_in_nums_outputed(outputs, _inputs4local_layout)
    params = [
        *boundings.values(), 
        # *penalty4island_connectivity, \
        total_overbounds_of_parallel2x4storage, total_overbounds_of_storage, total_overbounds_of_printer_sets, 
        total_insufficiency_of_accompaniment_seats, total_bound_in_accompaniment_seats_without_islands, 
        overbounds_within_main_zones, total_overbounds_of_high_cabinets_near_wall, \
        overbounds_within_sub_zones
    ]

    params = [10**50 * penalty for penalty in params]

    if 'islandSpaceing' in inputs4local_layout.keys():
        params += [-num_of_persons]

    storage_opts = ['locker', 'cabinet']
    for prior in _priorities:
        if prior not in ['sub_zones', 'main_zones_walls_in_axises']: continue

        for subject in storage_opts:
            params += list(chain.from_iterable(penalties_in_order_of_priority[prior][subject]))
    return params