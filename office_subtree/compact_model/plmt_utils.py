import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from general.latest_spacing import spacing as latest_spacing, main_passageway_width, __map_side_to_index
from general.configs import sizes


def __get_spacing_for_each_boundary(subject, subject_side,
                                    boundary, axis='X', 
                                    exists_main_passageway=False, user_main_passageway_width=None,
                                    latest_spacing=latest_spacing, main_passageway_width=main_passageway_width,
                                    sizes=sizes):
    if subject is None:
        return 0
    

    subject_spacing = latest_spacing[subject]

    neighbor, _ = boundary
    if neighbor in ['islands', 'virtual_wall4local_layout']:
        return sizes['chair'][1]
    
    # _components_near_walls = ['printer_set', 'big_lockers', 'high_cabinets']
    _components_near_walls = ['printer_set', 'storage', 'desk']
    if exists_main_passageway:
        against = 'main_passageway'
        spacing = subject_spacing[f'against_{against}'][__map_side_to_index(subject_side)] + \
                    user_main_passageway_width if user_main_passageway_width else main_passageway_width
    elif neighbor not in _components_near_walls:
        if neighbor == 'office_wall':
            against = 'window'
        else:
            against = neighbor
        spacing = subject_spacing[f'against_{against}'][__map_side_to_index(subject_side)]
    elif neighbor in _components_near_walls:
        # if neighbor in ['big_lockers', 'high_cabinets']:
        #     neighbor = 'storage'
            
        _, neighbor_parallel2x = boundary
        if axis == 'X':
            neighbor_side = 'longside' if neighbor_parallel2x else 'shortside'
        else:
            neighbor_side = 'shortside' if neighbor_parallel2x else 'longside'
        spacing = subject_spacing[f'against_{neighbor}'][__map_side_to_index(subject_side)][__map_side_to_index(neighbor_side)]

    return spacing