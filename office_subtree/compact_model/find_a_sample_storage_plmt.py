import math

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from general.configs import sizes, spacing
from general.utils import _calcu_nrows4subjects, _calcu_occupied_length_for_subjects


def find_a_compact_plmt4subjects_to_fill_storage(sub_zone, subject, parallel2x, upbounds_specific2parallel2xs,
                                                 subject_unit, storage_to_fill,
                                                 sizes=sizes):
    if storage_to_fill <= 0:
        return (0, 0)
    
    _, (X, Y) = sub_zone

    l, w = sizes['storage']
    specific_subject = ('big_' if subject == 'locker' else 'high_') + subject + 's'
    if parallel2x:
        max_nrows = _calcu_nrows4subjects(specific_subject, w, Y, spacing=spacing)
        min_ncols = 0
        while min_ncols * l <= X:
            if subject_unit * max_nrows * min_ncols >= storage_to_fill:
                break
            min_ncols += 1
        
        compact_matrix = (max_nrows, min_ncols)
    else:
        max_ncols = math.floor(Y / l)
        min_nrows = 0
        while _calcu_occupied_length_for_subjects(specific_subject, min_nrows, w) <= X:
            if  subject_unit * max_ncols * min_nrows >= storage_to_fill:
                break
            min_nrows += 1
                
        if specific_subject == 'high_cabinets':
            min_nrows = min(min_nrows, upbounds_specific2parallel2xs[specific_subject][0])
        compact_matrix = (min_nrows, max_ncols)
    return compact_matrix


def find_a_compact_plmt4two_col_cabinets_to_fill_storage(cabinet_upbound, num_of_cabinets_per_col,
                                                         cabinet_unit, storage_to_fill):
    min_num = 0
    while min_num <= cabinet_upbound:
        if cabinet_unit * num_of_cabinets_per_col*2 * min_num >= storage_to_fill:
            break
        min_num += 1
    return min_num
