from collections import defaultdict

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from general.configs import spacing, sizes
from general.utils import yield_shifts_for_subjects


def _yield_rects4subjects(RECT, num_of_subjects, width, self_spacing):
    origin, (X, Y) = RECT
    x, y = origin
    for i in range(num_of_subjects):
        yield ((x + width * i + self_spacing * i, y), (width, Y))


def unfold_RECTs_in_main_zone(RECTs, partial_individual, sizes=sizes, spacing=spacing):
    assert len(RECTs) == len(partial_individual) - 1

    num_of_two_col_islands, num_of_two_col_low_cabinets, has_mixed_cabinets_island, subject_near_wall, num_of_subjects_near_wall = partial_individual
    
    rectangles_dict = defaultdict(list)

    if num_of_two_col_low_cabinets > 0 and RECTs[0]:
        rectangles_dict['two_col_low_cabinets'] = list(_yield_rects4subjects(RECTs[0], num_of_two_col_low_cabinets, sizes['storage'][1]*2, spacing['cabinet']['against_self']['longside']))

    if has_mixed_cabinets_island and RECTs[1]:
        rectangles_dict['mixed_cabinets_island'] = [RECTs[1]]

    if num_of_two_col_islands > 0 and RECTs[-2]:
        rectangles = list(_yield_rects4subjects(RECTs[-2], num_of_two_col_islands, sizes['desk'][1]*2, spacing['desk']['against_self']['longside']))
        rectangles_dict['two_col_islands'] = rectangles
        l, w = sizes['storage']
        rectangles_dict['storage_below_two_col_islands'] = [((x + X/2 - l, y - w), (l * 2, w)) for (x, y), (X, Y) in rectangles]

    if num_of_subjects_near_wall > 0 and RECTs[-1]:
        subject = 'big_lockers' if subject_near_wall else 'high_cabinets'
        if subject == 'big_lockers':
            shifts = yield_shifts_for_subjects(subject, num_of_subjects_near_wall, sizes['storage'][1], spacing['locker']['against_self']['longside'])
        else:
            shifts = yield_shifts_for_subjects(subject, num_of_subjects_near_wall, sizes['storage'][1], spacing['cabinet']['against_self']['longside'])
        (_x, _y), (_X, _Y) = RECTs[-1]
        _rectangles = [((_x + shift, _y), (width, _Y)) for shift, width in shifts]
        rectangles_dict[subject] = [((_x + _X - x + _x - X, y), (X, Y)) for (x, y), (X, Y) in _rectangles]
        # rectangles_dict[subject] = _rectangles
    return rectangles_dict


def unfold_RECTs_in_sub_zone(RECTs, partial_individual, sizes=sizes, spacing=spacing):
    rectangles_dict = defaultdict(list)

    k, delta = 0, 3
    for subject, ((x, y), (X, Y)) in zip(['big_lockers', 'high_cabinets'], RECTs):
        parallel2x, nrows, ncols = partial_individual[k:k+delta]

        shifts = yield_shifts_for_subjects(subject, nrows, sizes['storage'][1], spacing['cabinet']['against_self']['longside'])
        rectangles_dict[subject] = [((x, y + shift), (X, width)) if parallel2x else ((x + shift, y), (width, Y))
                                    for shift, width in shifts]
        
        k += delta
    return rectangles_dict

