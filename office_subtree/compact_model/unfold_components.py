from collections import defaultdict

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from general.configs import sizes

def _get_components_by_unit(subject, rectangles, parallel2x, size):
    assert subject in ['big_lockers', 'high_cabinets'] + ['two_col_low_cabinets'] + ['mixed_low_caibinets', 'mixed_islands']

    l, w = size

    components = []
    for (x, y), (X, Y) in rectangles:
        if parallel2x:
            _nrows, _ncols = int(Y / w), int(X / l)
            for i in range(_nrows):
                components += [((x + l * j, y + i * w), (l, w)) for j in range(_ncols)]
        else:
            _nrows, _ncols = int(X / w), int(Y / l)
            for i in range(_nrows):
                components += [((x + w * i, y + l * j), (w, l)) for j in range(_ncols)]
    return components


def _get_components4two_col_islands(rectangles, size):
    l, w = size
    
    desks_in_unit3, desks_in_unit  = [], []
    for (x, y), (X, Y) in rectangles:
        unit3, unit = l * 3, l
        num_of_unit3s = int(Y / unit3)
        num_of_units = int((Y % unit3) / unit)
        desks_in_unit3 += [((x, y + unit3 * j), (X, unit3)) for j in range(num_of_unit3s)]
        desks_in_unit += [((x, y + unit3 * num_of_unit3s + unit * j), (X, unit)) for j in range(num_of_units)]

    return desks_in_unit3, desks_in_unit


def _get_components4mixed_cabinets_island(rectangle, sizes):
    origin, (X, Y) = rectangle

    size = sizes['storage']
    storage_rectangle = ((origin, (size[1], Y)))
    low_cabinets = _get_components_by_unit('mixed_low_caibinets', [storage_rectangle], False, size)

    l, w = sizes['desk']
    x, y = origin
    desk_rectangle = ((x + sizes['storage'][1], y), (w, Y))
    # desks = _get_components_by_unit('mixed_islands', [desk_rectangle], False, size)
    (x, y), (X, Y) = desk_rectangle
    unit3 = l * 3
    mixed_desks_in_unit3 = [((x, y + unit3 * j), (X, unit3)) for j in range(int(Y/unit3))]
    return (low_cabinets, mixed_desks_in_unit3)


def unfold_components_in_sub_zone(rectangles_dict, partial_individual, sizes=sizes):
    components_dict = defaultdict(list)

    k, delta = 0, 3
    for subject in ['big_lockers', 'high_cabinets']:
        parallel2x, *_ = partial_individual[k:k+delta]
        components_dict[subject] = _get_components_by_unit(subject, rectangles_dict[subject], parallel2x, sizes['storage'])
        k += delta
    return components_dict


def unfold_components_in_main_zone(rectangles_dict, sizes=sizes):
    components_dict = defaultdict(list)

    for subject, rectangles in rectangles_dict.items():
        if subject == 'two_col_islands':
            desks_in_unit3, desks_in_unit = _get_components4two_col_islands(rectangles, sizes['desk'])
            if desks_in_unit3:
                components_dict['desks_in_unit3'] += desks_in_unit3
            if desks_in_unit:
                components_dict['desks_in_unit1'] += desks_in_unit
        elif subject == 'mixed_cabinets_island':
            low_cabinets, desks = _get_components4mixed_cabinets_island(rectangles[0], sizes)
            components_dict['low_cabinets'] += low_cabinets
            components_dict['mixed_desks_in_unit3'] += desks
        elif subject == 'storage_below_two_col_islands':
            components_dict[subject] += [((x + X/2 * j, y),  (X/2, Y)) for (x, y), (X, Y) in rectangles for j in range(2)]
        else:
            _subject = 'low_cabinets' if subject == 'two_col_low_cabinets' else subject
            components_dict[_subject] += _get_components_by_unit(subject, rectangles, False, sizes['storage'])
    
    return components_dict