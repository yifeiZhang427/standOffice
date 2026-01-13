from .utils_for_zone_identification import _get_walls, _adapt_a_zone, _get_walls4nonrectangle_boundary


def _get_boundary_againsts4main_zone(axises, main_zone, rect_boundary, offices, reception, boundary_against=('wall', 'wall'), door=None, 
                                     boundary_lines=None):
    main_zone_walls = _get_walls(*main_zone.bounds)
    rect_boundary_walls = _get_walls(*rect_boundary.bounds)
    # if boundary_lines:
    #     # layout_walls = _get_walls4nonrectangle_boundary(layout_boundary)

    #     filtered_rect_boundary_walls = {}
    #     for axis, line in rect_boundary_walls.items():
    #         intersected_layout_lines = [l for l in boundary_lines if line.intersection(l).length > 0]
    #         if intersected_layout_lines:
    #             layout_line = intersected_layout_lines[0]
    #             if layout_line.length < line.length:
    #                 filtered_rect_boundary_walls[axis] = line.intersection(layout_line)
    #         else:
    #             filtered_rect_boundary_walls[axis] = line
    #     rect_boundary_walls = filtered_rect_boundary_walls

    reception_walls = _get_walls(*reception.bounds) if reception else {}

    # boundary_againsts = tuple(['office_wall' if any(main_zone_walls[axis].intersection(office).length > 0 for office in offices) else 
    #                           'wall' if any(main_zone_walls[axis].intersection(boundary_wall).length > 0 for boundary_wall in boundary_walls.values())
    #                                     or any(main_zone_walls[axis].intersection(reception_wall).length > 0 for reception_wall in reception_walls.values()) else 
    #                           'islands' for axis in axises])

    def __get_intersected_wall_with_boundary(wall, boundary_walls, door=None):
        for line in boundary_walls:
            if line.intersection(wall).length > 0:
                intersected_line = line.intersection(wall)
                # if door is not None and intersected_line.intersection(door).length > 0:
                #     intersected_line = difference(intersected_line, door)
                return intersected_line
        return None
    
    _boundary_againsts = []
    for axis in axises:
        exists_main_passageway = False
        
        wall = main_zone_walls[axis]
        # if any(wall.intersection(office).length > 0 for office in offices):
        if any(wall.intersects(office) for office in offices):
            boundary_against = ('office_wall', None)

            exists_main_passageway = True
        elif any(wall.intersection(b_wall).length > 0 for b_wall in rect_boundary_walls.values()):
            # if axis == '+y':
            #     _boundary = 'window'    
            #     # for supporting the case that accompany seats can not be placed in front of storages/printer sets, according to the specifics about spacing
            # else:
            #     _boundary = 'wall'

            if boundary_lines:
                lines = [line for line in boundary_lines if line.intersection(wall).length > 0]
                if not lines:
                    boundary_against = ('islands', None)
                else:
                    boundary_against = ('wall', lines[0].intersection(wall))
            else:
                boundary_against = ('wall', __get_intersected_wall_with_boundary(wall, rect_boundary_walls.values()))

            if axis == '-y':
                exists_main_passageway = True
        elif any(wall.intersection(r_wall).length > 0 for r_wall in reception_walls.values()):
            boundary_against = ('wall', __get_intersected_wall_with_boundary(wall, reception_walls.values(), door=door))

            exists_main_passageway = True
        else:
            boundary_against = ('islands', None)
        _boundary_againsts.append((*boundary_against, exists_main_passageway))

    return _boundary_againsts


def _get_storage_orientation4sub_zone(axis):
    return 1 if axis.endswith('x') else 0

def _get_wall_location4sub_zone(axis):
    if axis.endswith('x'):
        wall_location = ('left' if axis.split('x')[0] == '-' else 'right')
    else:
        wall_location = ('down' if axis.split('y')[0] == '-' else 'up')
    return wall_location
    

def determine_parameters_for_component_placements(reception, offices, boundary,
                                                  door, _sub_zones, _main_zones,
                                                  boundary_lines=None):
    boundary_against_in_Y_axis4main_zones = [_get_boundary_againsts4main_zone(['-y', '+y'], _main_zone, boundary, offices, reception, boundary_lines=boundary_lines) for _main_zone in _main_zones]
    boundary_against4main_zones = [_get_boundary_againsts4main_zone(['-x', '+x'], _main_zone, boundary, offices, reception, boundary_lines=boundary_lines) for _main_zone in _main_zones]
    for i, ((S, N), (W, E)) in enumerate(zip(boundary_against_in_Y_axis4main_zones, boundary_against4main_zones)):
        print(f'\t {i}: (N, S, W, E) = ({N}, {S}, {W}, {E})\n')

    main_zones = [_adapt_a_zone(_main_zone) for _main_zone in _main_zones]
    desk_orientations4main_zones = [0] * len(main_zones)
    passageway_locations4main_zones = ['down'] * len(main_zones)

    sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones = [], [], []
    for axis, zones in _sub_zones.items():
        if type(axis) == tuple:
            _, axis = axis
        for sub_zone in zones:
            adapted_zone = _adapt_a_zone(sub_zone)
            storage_orientations4sub_zone = _get_storage_orientation4sub_zone(axis)
            wall_locations4sub_zone = _get_wall_location4sub_zone(axis)
            sub_zones.append(adapted_zone)
            storage_orientations4sub_zones.append(storage_orientations4sub_zone)
            wall_locations4sub_zones.append(wall_locations4sub_zone)

    return main_zones, desk_orientations4main_zones, passageway_locations4main_zones, \
            boundary_against_in_Y_axis4main_zones, boundary_against4main_zones, \
            sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, boundary
