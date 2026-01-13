
from shapely.geometry import Polygon, Point, LineString, MultiPoint
from shapely import envelope, difference
from shapely.ops import split
from shapely import affinity

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from zone_identification.utils_for_zone_identification import _get_walls, _get_walls4nonrectangle_boundary


def _rotate_a_zone(zone, rotation, center=(0, 0)):
    # rotated_points = rotate_back_new(zone.exterior.coords, math.radians(rotation))
    # rotated_zone = envelope(MultiPoint(rotated_points))
    
    rotated_zone = affinity.rotate(zone, rotation, origin=center)
    return rotated_zone


def _rotate_a_point(door, rotations4cutted_zone, boundary_centriod):
    rotated_door = affinity.rotate(door, rotations4cutted_zone, origin=boundary_centriod)
    return rotated_door

def _rotate_a_line(line, rotations4cutted_zone, boundary_centriod):
    rotated_line = affinity.rotate(line, rotations4cutted_zone, origin=boundary_centriod)
    return rotated_line


def _find_offices_inside_cutted_zone(offices, cutted_zone):
    offices_inside = []

    for office in offices:            
        if cutted_zone.contains(office):
            offices_inside.append(office)
        else:
            intersection = office.intersection(cutted_zone)
            if intersection.area > 0:
                box = envelope(MultiPoint(intersection.exterior.coords))
                offices_inside.append(box)

    return offices_inside

def _find_office_doors_inside_cutted_zone(office_doors, offices_inside, offices, cutted_zone):
    office_doors_inside = []

    __find_office_doors = lambda office, office_doors: [door for door in office_doors if office.intersection(door).length > 0]

    for office_inside in offices_inside:
        its_offices = [office for office in offices if office.intersection(office_inside).area > 0]
        if not its_offices: continue

        office = its_offices[0]

        doors4office = __find_office_doors(office, office_doors)
        if not doors4office: continue

        door = doors4office[0]
        if office_inside.area < office.area:
            axis, line_in_office = [(axis, line) for axis, line in _get_walls(*office.bounds).items() if line.intersects(door)][0]
            line_inside = line_in_office.intersection(office_inside)
            office_doors_inside.append(line_inside)
        else:
            office_doors_inside.append(door)
    return office_doors_inside


def assign_components_to_cutted_zones(cutted_zones, 
                                     reception=None, offices=[], office_doors=[], main_door=None,
                                     boundary_lines=[]):
    reception_in_cutted_zones = [reception.intersection(cutted_zone) if reception.intersection(cutted_zone).area > 0 else None
                                 for cutted_zone in cutted_zones]

    offices_in_cutted_zones = [_find_offices_inside_cutted_zone(offices, cutted_zone) for cutted_zone in cutted_zones]
    office_doors_in_cutted_zones = [_find_office_doors_inside_cutted_zone(office_doors, offices_in_cutted_zone, offices, cutted_zone)
                                    for offices_in_cutted_zone, cutted_zone in zip(offices_in_cutted_zones, cutted_zones)]

    # office_doors_in_cutted_zones = [[window_door for window_door in office_doors if cutted_zone.intersection(window_door).length > 0] 
    #                                 for cutted_zone in cutted_zones]
    
    main_door_in_cutted_zones = [main_door if cutted_zone.contains(main_door) else None for cutted_zone in cutted_zones]

    boundary_lines_in_cutted_zones = [[line for line in boundary_lines if cutted_zone.intersection(line).length > 0]
                                    for cutted_zone in cutted_zones]
    return reception_in_cutted_zones, \
            offices_in_cutted_zones, office_doors_in_cutted_zones, main_door_in_cutted_zones,\
            boundary_lines_in_cutted_zones



_rotate_components_in_cutted_zones = lambda components_in_cutted_zones, _component_rotate_func, \
                                            rotations4cutted_zones={}, centriod=(0, 0): \
                                            [[_component_rotate_func(component, rotation, centriod) for component in components_in_cutted_zone]
                                                for components_in_cutted_zone, rotation in zip(components_in_cutted_zones, rotations4cutted_zones)]

def rotate_cutted_zones_and_components(cutted_zones, rotations4cutted_zones, centriod,
                                       reception_in_cutted_zones=[], offices_in_cutted_zones=[], office_doors_in_cutted_zones=[], main_door_in_cutted_zones=None,
                                       boundary_lines_in_cutted_zones=[]):
    
    rotated_cutted_zones = [_rotate_a_zone(zone, rotation, center=centriod) 
                            for zone, rotation in zip(cutted_zones, rotations4cutted_zones)]
    
    rotated_receptions = [_rotate_a_zone(reception, rotation, centriod) if reception else None 
                            for reception, rotation in zip(reception_in_cutted_zones, rotations4cutted_zones)]

    
    # rotated_offices_groups = [[_rotate_a_zone(office, rotation, center=centriod) for office in offices] 
    #                           for offices, rotation in zip(offices_in_cutted_zones, rotations4cutted_zones)]
    # rotated_office_doors_groups = [[__rotate_door(door, rotation, centriod) for door in doors4cutted_zone] 
    #                             for doors4cutted_zone, rotation in zip(office_doors_in_cutted_zones, rotations4cutted_zones)]
    # rotated_boundary_lines_groups = [[_rotate_line(line, rotation, centriod) for line in lines] 
    #                                  for lines, rotation in zip(boundary_lines_in_cutted_zones, rotations4cutted_zones)]

    rotated_offices_groups = _rotate_components_in_cutted_zones(offices_in_cutted_zones, _rotate_a_zone, rotations4cutted_zones=rotations4cutted_zones, centriod=centriod)
    rotated_office_doors_groups = _rotate_components_in_cutted_zones(office_doors_in_cutted_zones, _rotate_a_point, rotations4cutted_zones=rotations4cutted_zones, centriod=centriod)
    # rotated_main_doors_groups = _rotate_components_in_cutted_zones(main_doors_in_cutted_zones, _rotate_a_point)
    rotated_main_doors = [_rotate_a_point(door, rotation, centriod) if door else None
                          for door, rotation in zip(main_door_in_cutted_zones, rotations4cutted_zones)]
    
    rotated_boundary_lines_groups = _rotate_components_in_cutted_zones(boundary_lines_in_cutted_zones, _rotate_a_line, rotations4cutted_zones=rotations4cutted_zones, centriod=centriod)

    return rotated_cutted_zones, \
            rotated_receptions, rotated_offices_groups, rotated_office_doors_groups, rotated_main_doors, \
            rotated_boundary_lines_groups
    