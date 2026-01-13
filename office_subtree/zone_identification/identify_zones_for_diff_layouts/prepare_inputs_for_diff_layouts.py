from itertools import chain

from .identify_zones_for_LType import identify_zones4LType_like, _cut_LType_via_inner_vertex, _cut_LIType_via_inner_vertexes, \
                                        identify_zones4LType_like_when_exists_office_rooms


def _prepare_inputs(parameters4cutted_zones):
    main_zones = [main_zone for main_zone, desk_orientation, passageway_location, boundaries in parameters4cutted_zones]
    desk_orientations4main_zones = [desk_orientation for main_zone, desk_orientation, passageway_location, boundaries in parameters4cutted_zones]
    passageway_locations4main_zones = [passageway_location for main_zone, desk_orientation, passageway_location, boundaries in parameters4cutted_zones]
    boundary_against_in_Y_axis4main_zones = [boundary_against_in_Y_axis for main_zone, desk_orientation, passageway_location, (boundary_against_in_Y_axis, _) in parameters4cutted_zones]
    boundary_against4main_zones = [boundary_against for main_zone, desk_orientation, passageway_location, (_, boundary_against) in parameters4cutted_zones]
    return main_zones, desk_orientations4main_zones, passageway_locations4main_zones, boundary_against_in_Y_axis4main_zones, boundary_against4main_zones


def _prepare_inputs_when_exist_office_rooms(parameters4cutted_zones):
    a_list_main_zones = [main_zone for main_zone, *_ in parameters4cutted_zones]
    a_list_desk_orientations4main_zones = [desk_orientation for main_zone, desk_orientation, *_ in parameters4cutted_zones]
    a_list_passageway_locations4main_zones = [passageway_location for main_zone, desk_orientation, passageway_location, *_ in parameters4cutted_zones]
    a_list_boundary_against_in_Y_axis4main_zones = [boundary_against_in_Y_axis for main_zone, desk_orientation, passageway_location, boundary_against_in_Y_axis, *_ in parameters4cutted_zones]
    a_list_boundary_against4main_zones = [boundary_against for main_zone, desk_orientation, passageway_location, _, boundary_against, *_ in parameters4cutted_zones]

    a_list_of_sub_zones = [sub_zones for *_, sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, boundary in parameters4cutted_zones]
    a_list_of_storage_orientations4sub_zones = [storage_orientations4sub_zones for *_, sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, boundary in parameters4cutted_zones]
    a_list_of_wall_locations4sub_zones = [wall_locations4sub_zones for *_, sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, boundary in parameters4cutted_zones]
    a_list_of_boundaries4sub_zones = [[boundary]*len(sub_zones) for *_, sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, boundary in parameters4cutted_zones]
    
    __flatten_a_list_of_lists = lambda a_list_of_lists: list(chain.from_iterable(a_list_of_lists))
    return [__flatten_a_list_of_lists(a_list_of_lists) for a_list_of_lists in [
            a_list_main_zones, a_list_desk_orientations4main_zones, a_list_passageway_locations4main_zones, a_list_boundary_against_in_Y_axis4main_zones, a_list_boundary_against4main_zones,
            a_list_of_sub_zones, a_list_of_storage_orientations4sub_zones, a_list_of_wall_locations4sub_zones, a_list_of_boundaries4sub_zones]
            ]


def prepare_inputs_for_diff_layouts(data, layout_type='L-Type'):
    cut_layout_func = _cut_LType_via_inner_vertex if layout_type == 'L-Type' else _cut_LIType_via_inner_vertexes

    if data['singleRooms'] or data['non_office_area']:
        (boundary, door), (rotations4cutted_zones, boundary_centriod), \
            rotated_cutted_zones, rotated_main_door, rotated_receptions_in_cutted_zones, \
            rotated_doors_in_cutted_zones, offices_in_cutted_zones, sub_zones2main_zones, main_zones2cutted_zones, \
                parameters4cutted_zones = identify_zones4LType_like_when_exists_office_rooms(data, cut_layout_func=cut_layout_func)
        
        (main_zones, desk_orientations4main_zones, passageway_locations4main_zones, boundary_against_in_Y_axis4main_zones, boundary_against4main_zones,\
            sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, boundaries4sub_zones) = _prepare_inputs_when_exist_office_rooms(parameters4cutted_zones)
    
        return  (boundary, door), (rotations4cutted_zones, boundary_centriod), \
            (rotated_cutted_zones, rotated_main_door, rotated_receptions_in_cutted_zones,
            main_zones, desk_orientations4main_zones, passageway_locations4main_zones, boundary_against_in_Y_axis4main_zones, boundary_against4main_zones, \
            rotated_doors_in_cutted_zones, offices_in_cutted_zones, sub_zones2main_zones, main_zones2cutted_zones,
            sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, boundaries4sub_zones)
    else:
        (boundary, door), (rotations4cutted_zones, boundary_centriod), \
            rotated_cutted_zones, rotated_main_door, \
                parameters4cutted_zones= identify_zones4LType_like(data, cut_layout_func=cut_layout_func)

        main_zones, desk_orientations4main_zones, passageway_locations4main_zones, boundary_against_in_Y_axis4main_zones, boundary_against4main_zones = _prepare_inputs(parameters4cutted_zones)

        main_zones2cutted_zones = dict(zip(main_zones, range(len(main_zones))))
        return  (boundary, door), (rotations4cutted_zones, boundary_centriod), \
                (rotated_cutted_zones, rotated_main_door, [],
                main_zones, desk_orientations4main_zones, passageway_locations4main_zones, boundary_against_in_Y_axis4main_zones, boundary_against4main_zones, \
                [], [], {}, main_zones2cutted_zones,
                [], [], [], [])