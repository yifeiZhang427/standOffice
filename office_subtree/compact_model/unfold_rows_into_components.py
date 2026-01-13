from collections import defaultdict
from itertools import chain

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from general.configs import sizes, rotations_of_directions


def __unfold_a_partitioned_row_of_printer_sets(rectangles, sizes=sizes):
    _is_parallel2x = lambda rotation: rotation in [rotations_of_directions[direciton] for direciton in ['up', 'down']]

    printers, paper_shredders = [], []
    for ((x, y), (X, Y)), rotation in rectangles:
        if _is_parallel2x(rotation):
            l, w = sizes['printer']
            printer = (((x, y), (l, Y)), rotation)
            # paper_shredder = (((x + l, y), (X - l, Y)), rotation)

            l, w = sizes['paper_shredder']
            startX4next = x + X - l
            paper_shredder = (((startX4next, y), (l, Y)), rotation)
        else:
            l, w = sizes['printer']
            printer = (((x, y), (X, l)), rotation)
            # paper_shredder = (((x, y + l), (X, Y - l)), rotation)

            l, w = sizes['paper_shredder']
            startY4next = y + Y - l
            paper_shredder = (((x, startY4next), (X, l)), rotation)
        printers.append(printer)
        paper_shredders.append(paper_shredder)
    return printers, paper_shredders


def __unfold_a_row(subject, row, parallel2x=True, 
                   storage_near_wall=False, sizes=sizes):
    if storage_near_wall:
        RECT, rotation, shift4ncols = row
    else:
        RECT, rotation = row
        shift4ncols = 0

    (x, y), (X, Y) = RECT

    l, w = sizes[subject]
    ncols = int(X / l) if parallel2x else int(Y / l)
    row = [(((x + l * j, y), (l, Y)), rotation) if parallel2x else 
            (((x, y + l * j), (X, l)), rotation) for j in range(ncols + shift4ncols)]
    return row

def unfold_components_in_sub_zone(rows_dict, partial_individual, sizes=sizes):
    components_dict = defaultdict(list)

    l, w = sizes['storage']

    k, delta = 0, 3
    for subject in ['big_lockers', 'high_cabinets']:
        parallel2x, nrows, ncols = partial_individual[k:k+delta]

        for RECT in rows_dict[subject]:
            components_dict[subject] += __unfold_a_row('storage', RECT, parallel2x=parallel2x, storage_near_wall=True)
        k += delta
    return components_dict


def _get_components4two_col_islands(rectangles, size):
    l, w = size
    
    desks_in_unit3, desks_in_unit  = [], []
    for ((x, y), (X, Y)), rotation in (rectangles):
        unit3, unit = l * 3, l
        num_of_unit3s = int(Y / unit3)
        num_of_units = int((Y % unit3) / unit)
        desks_in_unit3 += [(((x, y + unit3 * j), (X, unit3)), rotation) for j in range(num_of_unit3s)]
        desks_in_unit += [(((x, y + unit3 * num_of_unit3s + unit * j), (X, unit)), rotation) for j in range(num_of_units)]

    return desks_in_unit3, desks_in_unit


def unfold_components_in_main_zone(rectangles_dict, inputs4global_layout=None,
                                   sizes=sizes, rotations_of_directions=rotations_of_directions):
    if inputs4global_layout:
        user_desk = (inputs4global_layout['tableWidth'], inputs4global_layout['tableHeight'])
    else:
        user_desk = sizes['desk']

    components_dict = defaultdict(list)

    for subject, rectangles in rectangles_dict.items():
        if not rectangles: continue

        if subject == 'printer_sets':
            printers, paper_shredders = __unfold_a_partitioned_row_of_printer_sets(rectangles)
            components_dict['printer'] = printers
            components_dict['paper_shredder'] = paper_shredders
        elif subject == 'accompaniment_seats':
            components_dict['accompaniment_seat_in_unit1'] += rectangles
        elif subject == 'two_col_islands':
            desks_in_unit3, desks_in_unit = _get_components4two_col_islands(rectangles, user_desk)
            components_dict['desks_in_unit3'] += desks_in_unit3
            components_dict['desks_in_unit1'] += desks_in_unit
        # elif subject == 'mixed_cabinets_island':
        #     low_cabinets, desks = []
        #     components_dict['low_cabinets'] += low_cabinets
        #     components_dict['mixed_desks_in_unit3'] += desks
        elif subject == 'mixed_low_cabinets':
            components_dict['low_cabinets'] += __unfold_a_row('storage', rectangles[0], parallel2x=False)
        elif subject == 'mixed_desks':
            desks_in_unit3, desks_in_unit = _get_components4two_col_islands(rectangles, user_desk)
            components_dict[f'{subject}_in_unit3'] += desks_in_unit3
            components_dict[f'{subject}_in_unit1'] += desks_in_unit
        elif subject == 'storage_below_two_col_islands':
            # components_dict[subject] += [((x + X/2 * j, y),  (X/2, Y)) for (x, y), (X, Y) in rectangles for j in range(2)]
            components_dict[subject] += chain.from_iterable([__unfold_a_row('storage', row, parallel2x=True) for row in rectangles])
        else:
            _subject = 'low_cabinets' if subject == 'two_col_low_cabinets' else subject
            # components_dict[_subject] += _get_components_by_unit(subject, rectangles, False, sizes['storage'])
            components_dict[_subject] += chain.from_iterable([__unfold_a_row('storage', row, parallel2x=False) for row in rectangles])
    return components_dict


def unfold_components_in_main_zone_for_local_layout(RECTs_dict, new_num_of_subjects_per_col, inputs4local_layout,
                                                    rotations_of_directions=rotations_of_directions, sizes=sizes):
    
    user_desk = (inputs4local_layout['width'], inputs4local_layout['height'])

    components_dict = defaultdict(list)

    for subject, one_cols_list in RECTs_dict.items():
        rotations4one_cols = [rotations_of_directions[direction] for direction in ['left', 'right']]

        if subject in ['two_col_islands', 'mixed_island']:
            RECTs = one_cols_list
            for i, RECT in enumerate(RECTs):
                if subject.startswith('mixed_'):
                    new_num_of_desks = new_num_of_subjects_per_col['mixed_desk' if 'mixed_desk' in new_num_of_subjects_per_col.keys() else 'desk']
                else:
                    new_num_of_desks = new_num_of_subjects_per_col['desk'][i] if type(new_num_of_subjects_per_col['desk']) is list else new_num_of_subjects_per_col['desk']
                origin, (X, Y) = RECT
                l, w = user_desk
                updated_RECT = (origin, (X, l * new_num_of_desks))
                # (x, y), (X, Y) = RECT
                # l, w = user_desk
                # nrows = int(X / w)
                # rectangles = [(((x + w*i, y), (w, Y)), rotation) for i, rotation in zip(range(nrows), rotations4one_cols) ]
                desks_in_unit3, desks_in_unit = _get_components4two_col_islands([(updated_RECT, rotations4one_cols[0])], user_desk)
                prefix = 'mixed_' if subject.startswith('mixed') else ''
                components_dict[f'{prefix}desks_in_unit3'] += desks_in_unit3
                components_dict[f'{prefix}desks_in_unit1'] += desks_in_unit
        elif 'storage' in subject:
            parallel2x = True if 'on_shortside' in subject else False
            for one_cols in one_cols_list:
                for one_col, rotation in zip(one_cols, rotations4one_cols):
                    if 'on_shortside' in subject:
                        rotation = rotations_of_directions['down']
                    for component, RECT in one_col.items():
                        components_dict[component] += __unfold_a_row('storage', (RECT, rotation), parallel2x=parallel2x)
    
    return components_dict