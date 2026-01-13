from collections import defaultdict
from itertools import chain

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from general.configs import spacing, sizes, storage_spacing
from general.utils import yield_shifts_for_subjects


def _get_rotations(subject, i, _nrows, parallel2x=True, near_wall=True):
    rotations = None
    if subject == 'big_lockers':
        if near_wall:
            if i == 0:
                rotations = [180]
            else:
                _rotations = [0, 180]
                rotations = _rotations[:_nrows]
        else:
            _rotations = [0, 180]
            rotations = _rotations[:_nrows]
    elif subject == 'high_cabinets':
        if i == 0:
            _rotations = [180]*2
            rotations = _rotations[:_nrows]
        else:
            rotations = [0] if _nrows == 1 else \
                        [0, 180] if _nrows == 2 else \
                        [0]*2 + [180] if _nrows == 3 else \
                        [0]*2 + [180]*2
    
    __rotate_by = lambda rotation, by=-90: (rotation + by) % 360
    if not parallel2x:
        rotations = [__rotate_by(rotation) for rotation in rotations]
    return rotations


def _reduce_ncols_by(subject, i, _nrows):
    if subject == 'big_lockers':
        _shifts = [0, 0]
        shifts = _shifts[:_nrows]
    elif subject == 'high_cabinets':
        if i == 0:
            _shifts = [0, -1]
            shifts = _shifts[:_nrows]
        else:
            shifts = [0] if _nrows == 1 else \
                        [0]*2 if _nrows == 2 else \
                        [-1, 0, 0] if _nrows == 3 else \
                        [-1, 0, 0, -1]
    return shifts


def _unfold_RECT_into_rows(RECT, subject, shifts, parallel2x, sizes=sizes, near_wall=True):
    (x, y), (X, Y) = RECT

    rows = []
    _, w = sizes['storage']
    for i, (shift, width) in enumerate(shifts):
        _nrows = int(width / w)
        rotations = _get_rotations(subject, i, _nrows, parallel2x=parallel2x, near_wall=near_wall)
        shifts4ncols = _reduce_ncols_by(subject, i, _nrows)

        rects = [((x, y + shift + w * j), (X, w)) if parallel2x else ((x + shift + w * j, y), (w, Y))for j in range(_nrows)]
        rows += [(rect, rotation, shift4ncols) for rect, rotation, shift4ncols in zip(rects, rotations, shifts4ncols)]
    return rows


def unfold_RECTs_in_sub_zone(printer_sets4sub_zone, RECTs, partial_individual, sizes=sizes, spacing=spacing):
    _, num_of_printer_sets = printer_sets4sub_zone
    
    rectangles_dict = defaultdict(list)

    k, delta = 0, 3
    for subject, RECT in zip(['big_lockers', 'high_cabinets'], RECTs):
        parallel2x, nrows, ncols = partial_individual[k:k+delta]

        # shifts = yield_shifts_for_subjects(subject, nrows, sizes['storage'][1], spacing['cabinet']['against_self']['longside'])
        # # (x, y), (X, Y) = RECT
        # # rectangles_dict[subject] = [((x, y + shift), (X, width)) if parallel2x else ((x + shift, y), (width, Y))
        # #                             for shift, width in shifts]
        
        # rectangles_dict[subject] = _unfold_RECT_into_rows(RECT, subject, shifts, parallel2x)

        near_wall = True if parallel2x else (False if num_of_printer_sets > 0 else True)
        shifts = yield_shifts_for_subjects(subject, nrows, sizes['storage'][1], spacing['cabinet']['against_self']['longside'], near_wall=near_wall)
        rectangles_dict[subject] = _unfold_RECT_into_rows(RECT, subject, shifts, parallel2x, near_wall=near_wall)

        k += delta
    return rectangles_dict

def unfold_RECTs_in_partitions(relative_RECTs_in_partitions, relative_plmts_in_partitions, boundary_against4partitioned_zones, 
                               sizes=sizes, storage_spacing=storage_spacing):
    rectangles_dict = defaultdict(list)

    l, w = sizes['storage']
    for RECTs, plmts, boundary_against in zip(relative_RECTs_in_partitions, relative_plmts_in_partitions, boundary_against4partitioned_zones):
        (left_neighbor, _), _ = boundary_against
        for RECT, (subject, (parallel2x, nrows, ncols)) in zip(RECTs, plmts.items()):
            if nrows * ncols == 0: continue
            
            near_wall = True if parallel2x else (False if left_neighbor != 'wall' else True)
            shifts = yield_shifts_for_subjects(subject, nrows, w, storage_spacing, near_wall=near_wall)
            rectangles_dict[subject] += _unfold_RECT_into_rows(RECT, subject, shifts, parallel2x, near_wall=near_wall)
    return rectangles_dict


def _yield_rects4subjects(RECT, num_of_subjects, width, self_spacing, Ys=[]):
    origin, (X, Y) = RECT
    x, y = origin
    for i in range(num_of_subjects):
        if Ys:
            Y = Ys[i]
        yield ((x + width * i + self_spacing * i, y), (width, Y))

        
def _yield_rows4subjects(RECT, subject, rotations, num_of_subjects, width, self_spacing, sizes=sizes):
    assert subject in ['storage']

    _, w = sizes[subject]

    origin, (X, Y) = RECT
    x, y = origin
    for i in range(num_of_subjects):
        shift = width * i + self_spacing * i
        # yield ((x + width * i + self_spacing * i, y), (width, Y))
        _nrows = int(width / w)
        # rotations = [90, 270]
        rects = [((x + shift + w * j, y), (w, Y)) for j in range(_nrows)]
        rows = [(rect, rotation) for rect, rotation in zip(rects, rotations)]
        yield rows


def unfold_RECTs_in_main_zone(new_num_of_subjects_per_col, RECTs, partial_individual, 
                              inputs4global_layout=None,
                              sizes=sizes, spacing=spacing):
    if inputs4global_layout:
        user_desk = (inputs4global_layout['tableWidth'], inputs4global_layout['tableHeight'])
        user_desk_spacing = inputs4global_layout['islandSpaceing']
    else:
        user_desk = user_desk
        user_desk_spacing = spacing['desk']['against_self']['longside']

    
    # assert len(RECTs) == len(partial_individual) - 1
    assert len(RECTs) - 1 == len(partial_individual)

    num_of_two_col_islands, num_of_two_col_low_cabinets, has_mixed_cabinets_island = partial_individual
    # , subject_near_wall, num_of_subjects_near_wall = partial_individual
    
    rectangles_dict = defaultdict(list)

    if num_of_two_col_low_cabinets > 0 and RECTs[0]:
        rotations = [270, 90]
        rectangles_dict['two_col_low_cabinets'] = list(chain.from_iterable(_yield_rows4subjects(RECTs[0], 'storage', rotations, num_of_two_col_low_cabinets, sizes['storage'][1]*2, spacing['cabinet']['against_self']['longside'])))

    if has_mixed_cabinets_island and RECTs[1]:
        # rectangles_dict['mixed_cabinets_island'] = [RECTs[1]]
        (x, y), (X, Y) = RECTs[1]
        # this bug is related to the bi-directional placements of components within main zones.
        if 'mixed_desk' in new_num_of_subjects_per_col.keys():
            l, _ = user_desk
            Y = new_num_of_subjects_per_col['mixed_desk'] * l
        _, w = sizes['storage']     
        cabinet_rect = ((x, y), (w, Y))
        desk_rect = ((x + w, y), (X - w, Y))
        rotations = [270, 90]
        # rectangles_dict['mixed_cabinets_island'] = [(rect, rotation) for rect, rotation in zip([cabinet_rect, desk_rect], rotations)]
        rectangles_dict['mixed_low_cabinets'] = [(cabinet_rect, rotations[0])]
        rectangles_dict['mixed_desks'] = [(desk_rect, rotations[1])]

        l, w = sizes['storage']
        rotation = 0
        rectangles_dict['storage_below_two_col_islands'] += [(((cabinet_rect[0][0], y - w), (l * 2, w)), rotation)]

    if num_of_two_col_islands > 0 and RECTs[-2]:
        rectangles = list(_yield_rects4subjects(RECTs[-2], num_of_two_col_islands, user_desk[1]*2, user_desk_spacing,
                                                Ys=[] if type(new_num_of_subjects_per_col['desk']) is int else [user_desk[0] * num for num in new_num_of_subjects_per_col['desk']]))
        rectangles_dict['two_col_islands'] = [(rect, 90) for rect in rectangles]

        l, w = sizes['storage']
        _rectangles = [((x + X/2 - l, y - w), (l * 2, w)) for (x, y), (X, Y) in rectangles]
        # rotations = [0] * len(rectangles)
        rotation = 0
        rectangles_dict['storage_below_two_col_islands'] += [(rect, rotation) for rect in _rectangles]

    # if num_of_subjects_near_wall > 0 and RECTs[-1]:
    #     for RECT in RECTs[-1]:
    #         subject = 'big_lockers' if subject_near_wall else 'high_cabinets'
    #         if subject == 'big_lockers':
    #             shifts = yield_shifts_for_subjects(subject, num_of_subjects_near_wall, sizes['storage'][1], spacing['locker']['against_self']['longside'])
    #         else:
    #             shifts = yield_shifts_for_subjects(subject, num_of_subjects_near_wall, sizes['storage'][1], spacing['cabinet']['against_self']['longside'])
    #         (_x, _y), (_X, _Y) = RECT
    #         # _rectangles = [((_x + shift, _y), (width, _Y)) for shift, width in shifts]
    #         # # rectangles_dict[subject] = [((_x + _X - x + _x - X, y), (X, Y)) for (x, y), (X, Y) in _rectangles]
    #         # rectangles_dict[subject] = _rectangles

    #         rows = _unfold_RECT_into_rows(RECT, subject, shifts, False)
    #         reflected_rows = [(((_x + _X - x + _x - X, y), (X, Y)), (rotation + 180) % 360) for ((x, y), (X, Y)), rotation in rows]
    #         rectangles_dict[subject] += reflected_rows
    return rectangles_dict

