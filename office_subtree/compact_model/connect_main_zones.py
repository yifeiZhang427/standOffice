def connect_main_zones(index4main_zones, num_of_main_zones, individual):
    penalty = 0

    k, delta = index4main_zones
    for i in range(num_of_main_zones):
        partial_individual = individual[k:k+delta]
        _, num_of_two_col_low_cabinets, has_mixed_cabinets_island, _, num_of_subjects_near_wall = partial_individual

        if i == 0:
            if num_of_subjects_near_wall != 0:
                penalty += 1
        elif i == num_of_main_zones - 1:
           penalty += sum(1 if num != 0 else 0 for num in [num_of_two_col_low_cabinets, has_mixed_cabinets_island])
        else:
            penalty += sum(1 if num != 0 else 0 for num in [num_of_two_col_low_cabinets, has_mixed_cabinets_island, num_of_subjects_near_wall])
       
        k += delta
    return penalty


def specialized_main_zone_connection(boundary_against4main_zones, index4main_zones, individual):
    penalty = 0

    k, delta = index4main_zones
    for left_neighbor, right_neighbor in boundary_against4main_zones:
        partial_individual = individual[k:k+delta]
        _, num_of_two_col_low_cabinets, has_mixed_cabinets_island, _, num_of_subjects_near_wall = partial_individual

        if left_neighbor != 'window':
            if num_of_two_col_low_cabinets or has_mixed_cabinets_island:
                penalty += 1
        
        if right_neighbor != 'wall':
            if num_of_subjects_near_wall:
                penalty += 1
        
        k += delta
    return penalty

        
def connect_main_zones_in_general(RECTs_list, boundary_against4main_zones, _boundary_against4updated_main_zones):
    penalty4passageway = 0
    penalty4high_subjects_near_right_wall = 0
    penalty4cabinets = 0

    for i, (RECTs, (_, right_neighbor), (_, updated_right_neighbor)) in enumerate(zip(RECTs_list, boundary_against4main_zones, _boundary_against4updated_main_zones)):
        two_col_low_cabinets, mixed_cabinets_and_island, two_col_islands, subjects_near_wall = RECTs

        # if right_neighbor == 'main_passageway' and subjects_near_wall is not None:
        #     penalty4passageway += 1

        # if (right_neighbor != 'wall' or updated_right_neighbor != 'wall') and subjects_near_wall is not None:
        #     penalty4high_subjects_near_right_wall += 1
        # if i < len(RECTs_list) - 1 and subjects_near_wall is not None and any(subjects is not None for subjects in RECTs_list[i+1][:-1]):
        #     penalty4high_subjects_near_right_wall += 1


        if i > 0 and any(cabinets is not None for cabinets in [two_col_low_cabinets, mixed_cabinets_and_island]) and \
            any(any(desks is not None for desks in RECTs_list[_i][1:3]) for _i in range(i)):
            # any(desks is not None for desks in RECTs_list[i-1][1:3]):
            penalty4cabinets += 1


    return penalty4passageway, penalty4high_subjects_near_right_wall, penalty4cabinets