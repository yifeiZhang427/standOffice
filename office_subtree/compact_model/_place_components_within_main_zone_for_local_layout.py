from copy import deepcopy
from collections import defaultdict

from .bound_sub_model import _get_spacing_between
from .transform import transform_RECTs

from .plmt_utils import __get_spacing_for_each_boundary

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from general.configs import sizes
from general.utils import _calcu_occupied_length_for_subjects, _calcu_nrows4subjects


def ___place_low_storage_col_by_col(var_num_of_small_lockers, var_num_of_low_cabinets, one_col_RECT_in_Y_axis, sizes=sizes):
    l, w = sizes['storage']

    _RECTs_dict = {}
    _plmts_dict = {}
    remained_BOX_in_Y_axis = deepcopy(one_col_RECT_in_Y_axis)
    for remained_num, subjects in zip([var_num_of_small_lockers, var_num_of_low_cabinets], ['small_lockers', 'low_cabinets']):
        if remained_num <= 0: continue

        (_x, _y), (_X, _Y) = remained_BOX_in_Y_axis
        available_num_of_storage = int(_Y / l)
        if available_num_of_storage <= 0: continue

        required_num = min(remained_num, available_num_of_storage)
        if subjects == 'small_lockers':
            _plmts_dict[subjects] = required_num
        elif subjects == 'low_cabinets':
            _plmts_dict[subjects] = required_num
        
        # rects = [((_x, _y + l * i), (w, l)) for i in range(required_num)]
        RECT = ((_x, _y), (w, l*required_num))
        _RECTs_dict[subjects] = RECT
        remained_BOX_in_Y_axis = ((_x, _y + l * required_num), (_X, _Y - l * required_num))

    return _RECTs_dict, _plmts_dict
    

def __place_islands_and_low_storage(num_of_islands_dict, 
                                    var_num_of_low_cabinets, var_num_of_small_lockers, 
                                    relative_main_zone, boundary_against4_main_zone, 
                                    user_desk, user_desk_spacing=None, sizes=sizes):
    if user_desk:
        _, desk_width = user_desk
    else:
        _, desk_width = sizes['desk']

    (_, y), (_, Y) = relative_main_zone

    remained_var_num_of_low_cabinets, remained_var_num_of_small_lockers = var_num_of_low_cabinets, var_num_of_small_lockers

    RECTs_dict = defaultdict(list)
    remained_BOX = deepcopy(relative_main_zone)
    updated_boundary_against4remained_BOX = list(boundary_against4_main_zone)
    for islands, num_of_islands in num_of_islands_dict.items():
        if islands == 'two_col_islands':
            boundary_of_islands = [('desk', False)] * 2 
            length = desk_width * 2
            new_left_boundary = ('desk', False)
        else:
            boundary_of_islands = [('desk', False), ('storage', False)]
            length = desk_width + sizes['storage'][1]
            new_left_boundary = ('storage', False)

        for i in range(num_of_islands):        
            # left_spacing, right_spacing = [_get_spacing_between(sub_subject, boundary) for sub_subject, boundary in zip(boundary_of_islands, updated_boundary_against4remained_BOX)] 
            left_spacing, right_spacing = [__get_spacing_for_each_boundary(sub_subject, 'longside', boundary, axis='Y') for (sub_subject, _), boundary in zip(boundary_of_islands, updated_boundary_against4remained_BOX)] 
            if user_desk_spacing is not None:
                if i > 0 or num_of_islands_dict['mixed_island'] > 0:
                    left_spacing = user_desk_spacing

            (x, y), (X, Y) = remained_BOX
            if X - left_spacing - right_spacing < length: continue

            l, w = sizes['storage']
            if remained_var_num_of_small_lockers > 0 or remained_var_num_of_low_cabinets > 0:
                # rects = [((x + left_spacing + l * i, y), (l, w)) for i in range(2)]
                RECT = ((x + left_spacing + desk_width - l, y), (l*2, w))
                if remained_var_num_of_small_lockers > 0:
                    RECTs_dict[f'storage_on_shortside_of_{islands}'] += [[{'small_lockers': RECT}]]
                    remained_var_num_of_small_lockers -= 2
                elif remained_var_num_of_low_cabinets > 0:
                    RECTs_dict[f'storage_on_shortside_of_{islands}'] += [[{'low_cabinets': RECT}]]
                    remained_var_num_of_low_cabinets -= 2
            
                _y, _Y = y + w, Y - w
            else:
                _y, _Y = y, Y
            
            if islands == 'mixed_island':
                length = desk_width
            RECT = ((x + left_spacing, _y), (length, _Y))
            RECTs_dict[islands].append(RECT)
            remained_BOX = ((x + left_spacing + length, y), (X - left_spacing - length, Y))
            updated_boundary_against4remained_BOX[0] = new_left_boundary


        if islands == 'mixed_island' and RECTs_dict[islands] and (remained_var_num_of_small_lockers > 0 or remained_var_num_of_low_cabinets > 0):
            (_x, _y), (_X, _Y) = RECTs_dict[islands][-1]
            _, w = sizes['storage']
            # one_col_RECT_in_Y_axis = ((_x + w, _y), (w, _Y))
            one_col_RECT_in_Y_axis = ((_x + _X, _y), (w, _Y))
            sub_RECTs_dict, sub_plmts_dict = ___place_low_storage_col_by_col(remained_var_num_of_small_lockers, remained_var_num_of_low_cabinets, one_col_RECT_in_Y_axis)
            RECTs_dict[f'storage_on_longside_of_{islands}'] += [[sub_RECTs_dict]]
            for subject, num_of_subjects in sub_plmts_dict.items():
                if subject == 'small_lockers':
                    remained_var_num_of_small_lockers -= num_of_subjects
                elif subject == 'low_cabinets':
                    remained_var_num_of_low_cabinets -= num_of_subjects

        
    
    _, (X, Y) = remained_BOX
    if remained_var_num_of_small_lockers > 0 or remained_var_num_of_low_cabinets > 0 and X > 0:
        _, w = sizes['storage']
        max_num_of_cols4storage = int(X / w)
        num_of_two_cols, has_one_col = int(max_num_of_cols4storage / 2), max_num_of_cols4storage % 2
        new_left_boundary = ('storage', False)
        for _, is_two_col in zip(range(num_of_two_cols + has_one_col), [True]*num_of_two_cols + [has_one_col]):
            left_spacing, right_spacing = [_get_spacing_between(sub_subject, boundary) for sub_subject, boundary in zip(boundary_of_islands, updated_boundary_against4remained_BOX)] 
            (x, y), (X, Y) = remained_BOX
            if X - left_spacing - right_spacing < length: continue

            rects_by_cols = []
            l, w = sizes['storage']
            one_col_RECTs_in_Y_axis = [((x + left_spacing + w * i, y), (w, Y)) for i in range(2 if is_two_col else 1)]
            for one_col_RECT_in_Y_axis in one_col_RECTs_in_Y_axis:
                sub_RECTs_dict, sub_plmts_dict = ___place_low_storage_col_by_col(remained_var_num_of_small_lockers, remained_var_num_of_low_cabinets, one_col_RECT_in_Y_axis)
                rects_by_cols += [sub_RECTs_dict]
                for subject, num_of_subjects in sub_plmts_dict.items():
                    if subject == 'small_lockers':
                        remained_var_num_of_small_lockers -= num_of_subjects
                    elif subject == 'low_cabinets':
                        remained_var_num_of_low_cabinets -= num_of_subjects
            RECTs_dict['storage_col_by_col'] += [rects_by_cols]
            length = w*2 if is_two_col else w
            remained_BOX = ((x + left_spacing + length, y), (X - left_spacing - length, Y))
            updated_boundary_against4remained_BOX[0] = new_left_boundary             

    num_of_low_cabinets, num_of_small_lockers = var_num_of_low_cabinets - remained_var_num_of_low_cabinets, var_num_of_small_lockers - remained_var_num_of_small_lockers
    return RECTs_dict, num_of_low_cabinets, num_of_small_lockers


def __reflect_around_Y_axis(RECT, zone, origin):
    __x, __y = origin
    (_x, _y), (_X, _Y) = zone

    (x, y), (X, Y) = RECT
    reflected_RECT = ((_x + _X - x + _x - X + __x, y + __y), (X, Y))
    return reflected_RECT


def _place_components_within_main_zone_for_local_layout(partial_individual, var_num_of_low_cabinets, var_num_of_small_lockers,
                                                        main_zone, boundary_against4_main_zone,
                                                        user_desk=None, user_desk_spacing=None):
    num_of_two_col_islands, _, has_mixed_cabinets_island = partial_individual
    num_of_one_col_islands = num_of_two_col_islands + has_mixed_cabinets_island

    num_of_islands_dict = {
        'two_col_islands': num_of_one_col_islands,
        'mixed_island': has_mixed_cabinets_island
    }

    reflect_around_Y_axis = True
    origin, (X, Y) = main_zone
    _relative_main_zone = ((0, 0), (X, Y))
    if reflect_around_Y_axis:
        _boundary_against4_main_zone = boundary_against4_main_zone[::-1] 
    else:
        _boundary_against4_main_zone = deepcopy(boundary_against4_main_zone)

    relative_RECTs_dict, num_of_low_cabinets, num_of_small_lockers = __place_islands_and_low_storage(num_of_islands_dict, 
                                                                                                    var_num_of_low_cabinets, var_num_of_small_lockers, 
                                                                                                    _relative_main_zone, _boundary_against4_main_zone,
                                                                                                    user_desk=user_desk, user_desk_spacing=user_desk_spacing)

    if reflect_around_Y_axis:
        RECTs_dict = {key: [__reflect_around_Y_axis(relative_RECT, _relative_main_zone, origin) for relative_RECT in relative_RECTs[::-1]] if key in ['two_col_islands', 'mixed_island'] else 
                            [[{sub_key: __reflect_around_Y_axis(RECT, _relative_main_zone, origin) for sub_key, RECT in one_col.items()} for one_col in one_cols[::-1]] for one_cols in relative_RECTs[::-1]]
                      for key, relative_RECTs in relative_RECTs_dict.items()}
    else:
        RECTs_dict = relative_RECTs_dict
    
    return RECTs_dict, num_of_low_cabinets, num_of_small_lockers
