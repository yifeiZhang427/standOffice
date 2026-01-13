import math

from .configs import sizes, spacing, spacing_in_4D
from .latest_spacing import spacing as latest_spacing, __map_side_to_index


def _calcu_nrows4subjects(subject, w, bound, 
                          self_spacing=None, desk_w4mixed=None,
                          spacing=spacing, near_wall=True, sizes=sizes):
    if subject in ['two_col_islands', 'low_cabinets']:
        # if subject == 'two_col_islands':
        #     self_spacing = spacing['desk']['against_self']['longside']
        #     _, w = sizes['desk']
        # else:
        #     self_spacing = spacing['cabinet']['against_self']['longside']
        #     _, w = sizes['storage']
        
        _subject = 'desk' if subject == 'two_col_islands' else 'storage'
        if w is None:
            _, w = sizes[_subject]

        if self_spacing is None:
            self_spacing = spacing['desk']['against_self']['longside']

        m = 0
        unit = w * 2
        while bound >= unit:
            m += 1
            bound -= unit + self_spacing
    elif subject == 'big_lockers':
        self_spacing = spacing['locker']['against_self']['longside']

        m = 0
        if near_wall:
            if bound >= w:
                m = 1
                bound -= w + self_spacing
        while bound >= 2*w:
            m += 2
            bound -= 2*w + self_spacing
        if bound >= w:
            m += 1
    elif subject == 'high_cabinets':
        self_spacing = spacing['cabinet']['against_self']['longside']

        # m = 2 if bound > 2*w else 1 if bound > w else 0
        # if bound >= 2*w + self_spacing:
        #     m += min(int((bound - w - self_spacing) / w), 4)
        m = 0
        if bound >= 2*w:
            m += 2
            bound -= 2*w + self_spacing
        while bound >= 4*w:
            m += 4
            bound -= 4*w + self_spacing
        if bound > w:
            m += int(bound / w)

        # m = min(m, 6)
    elif subject == 'mixed_island':
        length = sizes['storage'][1] + desk_w4mixed if desk_w4mixed is not None else sum([sizes[component][1] for component in ['storage', 'desk']])
        m = 1 if bound >= length else 0
    return m


def calcu_max_cols4printer_sets_alongside_wall(X, sizes=sizes, latest_spacing=latest_spacing):
    l, _ = sizes['printer_set']
    shortside_index = __map_side_to_index('shortside')
    shortside_spacing = latest_spacing['printer_set']['against_printer_set'][shortside_index][shortside_index]

    ncols = 0
    length = shortside_spacing
    while X - length >= l:
        ncols += 1
        length += l + shortside_spacing
    return ncols


def calcu_max_matrix_within_zone4subjects(subject, parallel2x, zone, sizes=sizes, spacing_in_4D=spacing_in_4D, near_wall=True):
    x, y = zone

    if not parallel2x:
        x, y = y, x

    if subject == 'printer_sets':
        l, w = sizes['printer_set']

        ncols = 0
        length = 0
        while x - length >= l:
            ncols += 1
            length += l + spacing_in_4D['printer_set']['against_printer_set'][1][1]

        nrows = None
    else:
        l, w = sizes['desk'] if subject == 'two_col_island' else sizes['storage']
        ncols = math.floor(x / l)
        nrows = _calcu_nrows4subjects(subject, w, y, near_wall=near_wall)
    return (nrows, ncols)

def calcu_compact_matrix_within_sub_zone4subjects(sub_zone, storage_orientation, 
                                                  subject, parallel2x, upbounds_specific2parallel2xs,
                                                  subject_unit, storage_to_fill,
                                                  sizes=sizes):
    if storage_to_fill <= 0:
        return (0, 0)
    
    _, (X, Y) = sub_zone

    if storage_orientation:
        X, Y = Y, X
        parallel2x = not parallel2x

    l, w = sizes['storage']
    specific_subject = ('big_' if subject == 'locker' else 'high_') + subject + 's'
    if parallel2x:
        max_nrows = _calcu_nrows4subjects(specific_subject, w, Y, spacing=spacing)
        min_ncols = 0
        while min_ncols * l <= X:
            if subject_unit * max_nrows * min_ncols >= storage_to_fill:
                # if min_ncols * l > X:
                #     min_ncols -= 1
                break
            min_ncols += 1
        
        # while subject_unit * max_nrows * min_ncols < storage_to_fill:
        #     min_ncols += 1
        #     if min_ncols * l >= X:
        #         break
        # if min_ncols * l > X:
        #     min_ncols -= 1
        compact_matrix = (max_nrows, min_ncols)
    else:
        max_ncols = math.floor(Y / l)
        min_nrows = 0
        while _calcu_occupied_length_for_subjects(specific_subject, min_nrows, w) <= X:
            if  subject_unit * max_ncols * min_nrows >= storage_to_fill:
                break
            min_nrows += 1
        # while subject_unit * max_ncols * min_nrows < storage_to_fill:
        #     min_nrows += 1
        #     if calcu_occupied_length_for_subjects(specific_subject, min_nrows, w) >= X:
        #         break
        # if calcu_occupied_length_for_subjects(specific_subject, min_nrows, w) > X:
        #     if min_nrows % 2 == 0:
        #         min_nrows -= 1
        #     else:
        #         min_nrows -= 2
                
        if specific_subject == 'high_cabinets':
            min_nrows = min(min_nrows, upbounds_specific2parallel2xs[specific_subject][0])
        compact_matrix = (min_nrows, max_ncols)
    return compact_matrix

def calcu_min_num_within_main_zone4two_col_cabinets(cabinet_upbound, num_of_cabinets_per_col,
                                                    cabinet_unit, storage_to_fill):
    min_num = 0
    while min_num <= cabinet_upbound:
        if cabinet_unit * num_of_cabinets_per_col*2 * min_num >= storage_to_fill:
            break
        min_num += 1
    return min_num

def _calcu_occupied_length_for_subjects(subject, num_of_subjects, w, 
                                        self_spacing=None, desk_w4mixed=None,
                                        spacing=spacing, near_wall=True):
    if subject == 'mixed_island':
        desk_w4desk = desk_w4mixed if desk_w4mixed else sizes['desk'][1]
        length = sizes['storage'][1] + desk_w4desk
    elif subject in ['low_cabinets', 'two_col_islands']:
        # if subject == 'low_cabinets': 
        #     _, w = sizes['storage']
        #     self_spacing = spacing['cabinet']['against_self']['longside']
        # else:
        #     _, w = sizes['desk']
        #     self_spacing = spacing['desk']['against_self']['longside']

        _subject = 'desk' if subject == 'two_col_islands' else 'storage'
        if w is None:
            _, w = sizes[_subject]

        if self_spacing is None:
            self_spacing = spacing['desk']['against_self']['longside']

        length = w*2 * num_of_subjects + self_spacing * (num_of_subjects - 1)
    elif subject == 'big_lockers':
        storage_spacing = spacing['locker']['against_self']['longside']

        length = 0
        num1 = num_of_subjects
        if near_wall:
            if num1 > 0:
                length += w
                num1 -= 1
        else:
            if num1 >= 2:
                length += w * 2
                num1 -= 2
            elif num1 >= 1:
                length += w
                num1 -= 1
        while num1 >= 2:
            length += storage_spacing + w * 2
            num1 -= 2
        if num1 >= 1:
            length += storage_spacing + w
    elif subject == 'high_cabinets':
        storage_spacing = spacing['locker']['against_self']['longside']

        length = 0
        num2 = num_of_subjects
        # if num2 > 0 and num2 <= 1:
        #     length += w 
        # elif num2 >= 2:
        #     length += w*2

        #     num2 = min(num2-2, 4)
        #     if num2 > 0:
        #         length += storage_spacing + w * num2

        if num2 > 0 and num2 <= 1:
            length += w 
            num2 -= 1
        elif num2 >= 2:
            length += w*2
            num2 -= 2

            while num2 >= 4:
                length += storage_spacing + w*4
                num2 -= 4

            if num2 > 0:
                length += storage_spacing + w*num2
    return length

def yield_shifts_for_subjects(subject, num_of_subjects, w, self_spacing, near_wall=True):
    if subject == 'big_lockers':
        length = 0
        num1 = num_of_subjects
        if near_wall:
            if num1 > 0:
                yield (length, w)
                length += w + self_spacing
                num1 -= 1

        while num1 >= 2:
            yield (length, w * 2)
            length += w * 2 + self_spacing
            num1 -= 2
        if num1 >= 1:
            yield (length, w)
            length += w + self_spacing
            num1 -= num1
    elif subject == 'high_cabinets':
        length = 0
        num2 = num_of_subjects

        if num2 > 0 and num2 <= 1:
            yield (length, w)
            length += w 
        elif num2 >= 2:
            yield (length, w*2)
            length += w*2 + self_spacing
            num2 -= 2

            while num2 >= 4:
                yield (length, w*4)
                length += w*4 + self_spacing
                num2 -= 4

            if num2 > 0:
                yield (length, w*num2)
                length += w*num2 + self_spacing
                num2 -= num2
    return length