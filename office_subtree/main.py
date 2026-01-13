import os
import json
from copy import deepcopy
from itertools import product, chain
import math
import datetime
import time
from collections import defaultdict

from shapely import envelope, MultiPoint, Point, LineString, GeometryCollection, Polygon
from shapely import affinity, difference
import matplotlib.pyplot as plt

import multiprocessing
from functools import partial
from .compact_model.run_ga import run
from .compact_model.connect_main_zones import specialized_main_zone_connection, connect_main_zones_in_general

from rotate_back_new_by_yifei import rotate_back_new

# from split_zones import split_zones
# from split_zones_ver2 import split_zones, identify_neighbors_in_X_axis_for_main_zones, split_zones_new, \
#                             identify_neighbors_in_Y_axis_for_main_zones
from general.inputs import main_zones, desk_orientations4main_zones, passageway_locations4main_zones, \
    sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, boundary
from zone_identification.identify_zones import prepare_inputs_without_reception
from zone_identification.identify_zones_when_exists_reception import prepare_inputs_with_reception
from zone_identification4local_layout.identify_region import identify_region

from zone_identification.identify_zones_for_diff_layouts.prepare_inputs_for_diff_layouts import prepare_inputs_for_diff_layouts
from zone_identification.identify_zones_for_diff_layouts.identify_zones_for_LType import __get_inner_vertexes

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))
from general.plot import plot_resulting_layout, plot_component_placements, plot_chairs


def write_json(data, filename, dp=None):
    if dp:
        if not os.path.exists(dp):
            os.makedirs(dp)
    else:
        dp = os.path.dirname(os.path.abspath(__file__))

    fp = os.path.join(dp, filename)
    with open(fp, 'w') as file:
        json.dump(data, file)


def read_json(filename, dp=None):
    if not dp:
        dp = os.path.dirname(os.path.abspath(__file__))

    data = None
    fp = os.path.join(dp, filename)
    with open(fp, 'r') as file:
        data = json.load(file)
    return data


types = [
    'printer_set', 'printer', 'paper_shredder',
    'desks_in_unit3', 'desks_in_unit1', 'mixed_desks_in_unit3', 'mixed_desks_in_unit1', 'accompaniment_seat_in_unit1',
    'big_lockers', 'small_lockers',
    'high_cabinets', 'low_cabinets',
    'chairs', 'accompaniment_chairs'
]
models = [
    'None', 'D2', 'D1',
    'T7', 'T8', 'T31', 'T15', 'T15',
    'L7', 'L6',
    'L10', 'L9',
    'C12-3', 'C3-1'
]


def add_ids(outputs, types=types, models=models):
    IDs = read_json(filename='IDs.json')
    types2models = dict(zip(types, models))
    models2ids = {item['key']: item['id'] for item in IDs}
    types2ids = {_type: models2ids[model] if model in models2ids.keys() else None for _type, model in
                 types2models.items()}

    furnitureDatas = []
    for _type, tlist in outputs.items():
        _id = types2ids[_type]
        for item in tlist:
            item['modelId'] = _id
            furnitureDatas.append(item)
    return furnitureDatas


def _adapt_a_zone(zone):
    minx, miny, maxx, maxy = zone.bounds
    origin = (minx, miny)
    rect = (maxx - minx, maxy - miny)
    return (origin, rect)



def _rotate_back(item, global_rotation, global_center=(0, 0)):
    item_back = deepcopy(item)

    center = (item['center']['x'], item['center']['y'])
    x_back, y_back = rotate_back_new([center], global_rotation, global_center)[0]
    item_back['center'] = {
        'x': x_back,
        'y': y_back
    }
    item_back['rotation'] = item['rotation'] - global_rotation
    return item_back

def _get_aggregated_targets(comp_dict_list):
    # components = set(comp for plmt in targets_dict_list for comp in plmt.keys())
    # aggregated_targets_dict = {comp: [RECT for plmt in targets_dict_list 
    #                                             if comp in plmt.keys()
    #                                                 for RECT in plmt[comp] ] 
    #                                     for comp in components}

    aggregated_components = defaultdict(list)
    for comp_dict in comp_dict_list:
        for comp, comp_list in comp_dict.items():
            aggregated_components[comp] += comp_list

    return aggregated_components

def _rotate_back_a_rect(component, angle, centroid=(0, 0)):
    rect, rotation = component
    if angle != 0:
        pass

    origin, (X, Y) = rect
    x, y = origin
    corners = [origin, (x + X, y + Y)]
    # original_corners = rotate_back_new(corners, -math.radians(angle))
    # new_box = envelope(LineString([Point(*corner) for corner in original_corners]))

    # original_corners = [affinity.rotate(Point(*point), -angle)for point in corners]
    box = envelope(LineString([Point(*corner) for corner in corners]))
    new_box = affinity.rotate(box, -angle, origin=centroid)

    minx, miny, maxx, maxy = new_box.bounds
    new_rect = ((minx, miny), (maxx - minx, maxy - miny))
    new_rotation = None if rotation is None else rotation - angle
    return new_rect if rotation is None else (new_rect, new_rotation)

def _rotate_back_door(door, angle, centroid=(0, 0)):
    door = affinity.rotate(door, -angle, centroid)
    return door

def _rotate_back_an_item(item, angle, centroid=(0, 0)):
    item_back = deepcopy(item)

    center = (item['center']['x'], item['center']['y'])
    center_back = affinity.rotate(Point(*center), -angle, origin=centroid)
    item_back['center'] = {
        'x': center_back.x,
        'y': center_back.y
    }
    item_back['rotation'] = item['rotation'] - math.radians(angle)
    return item_back

def rotate_back_components4zones(components_dict4zones, rotations4zones, centroid=(0, 0), in_output=True):
    components4main_zones_rotated_back = [{key: [_rotate_back_an_item(comp, rotation, centroid=centroid) if in_output else 
                                                 _rotate_back_a_rect(comp, rotation, centroid=centroid) for comp in comp_list] 
                                        # [{key: [_rotate_back_a_component(comp, rotation) for comp in comp_list] 
                                            for key, comp_list in components.items()} 
                                            for components, rotation in zip(components_dict4zones, rotations4zones)]
    return components4main_zones_rotated_back


def aggregate_components4main_zones(components_dict, storage_partition_below_two_col_islands, global_auto_layout=True):
    # aggregated_rectangles_dict = _get_aggregated_targets(rectangles_dict['main_zones'] + rectangles_dict['sub_zones'])
    # aggregated_components_dict = _get_aggregated_targets(list(chain.from_iterable(components_dict.values())))

    components_dict_list = components_dict['main_zones']
    if 'sub_zones' in components_dict.keys():
        components_dict_list += components_dict['sub_zones']
    aggregated_components_dict = _get_aggregated_targets(components_dict_list)

    if global_auto_layout:
        additional_storage_plmts = {}
        num4lockers, num4cabinets = storage_partition_below_two_col_islands
        if num4lockers and 'storage_below_two_col_islands' in aggregated_components_dict.keys():
            additional_storage_plmts['small_lockers'] = aggregated_components_dict['storage_below_two_col_islands'][:num4lockers]
        if num4cabinets:
            additional_storage_plmts['low_cabinets'] = aggregated_components_dict['storage_below_two_col_islands'][num4lockers:]
        if num4lockers or num4cabinets:
            if 'storage_below_two_col_islands' in aggregated_components_dict.keys():
                del aggregated_components_dict['storage_below_two_col_islands']
            aggregated_components_dict = {**aggregated_components_dict, **additional_storage_plmts}
    return aggregated_components_dict


def _get_inputs_for_global_auto_layout(params):
    inputs4global_layout = {key: value for key, value in params['userInput']['nonPublic']['officeArea'].items()
                            if key in [
                                "CabinetMagnification",
                                "fileCabinetFm",
                                "islandSpaceing",
                                "stepNumber",
                                "tableHeight",
                                "tableWidth"
                            ]}
    inputs4global_layout['mainHallway'] = params['userInput']['mainHallway']['width']
    return inputs4global_layout


def _write_out_furnitures(outputs, i, params, gloabal_roation=[0, (0, 0)]):
    furnitureDatas = add_ids(outputs)
    
    global_furnitureDatas = [_rotate_back(item, *gloabal_roation) for item in furnitureDatas]
    params['outPutMessage'][i]['furnitureDatas'].extend(global_furnitureDatas)

    params['algorithmMessage'][i]['components4visualization'] = {
        'boundary': boundary,
        'main_zones': main_zones,
        'sub_zones': sub_zones,
        'components': outputs,
        'chairs': outputs['chairs']
    }
    return params


def _plot_aggreated_components(components_dict_in_form_of_rects, storage_partition_below_two_col_islands, 
                               chairs, accompaniment_chairs,
                               zones, boundary, door, sub_dp,
                               main_zones=[], sub_zones=[], offices_group=[], doors_group=[], receptions=[]):
    aggreated_components = aggregate_components4main_zones(components_dict_in_form_of_rects, storage_partition_below_two_col_islands, global_auto_layout=True)
    ax = plot_component_placements(aggreated_components, zones, boundary, main_door=door,
                                   main_zones=main_zones, sub_zones=sub_zones, offices_group=offices_group, doors_group=doors_group, receptions=receptions,
                                    dp=sub_dp, fp='resulting_components.png')
    plot_chairs(ax, chairs + accompaniment_chairs, sub_dp, fp='resulting_chairs.png')

def convert_new_form_into_old_for_each_schema(schema):
    old_schema = {}

    for key, values in schema.items():
        if key == 'publicDoor':
            _center = lambda start, end: ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)
            old_schema[key] = [_center(*door['out']) for door in values][0]
        elif key == 'singleRooms':
            if values != []:
                old_schema[key] = list(chain.from_iterable([[room['out'] for room in rooms] for _, rooms in values.items()]))
            else:
                old_schema[key] = []
        elif key == 'singleRoomsDoor':
            if values != []:
                if 'singleRoomsDoor1' in schema.keys():
                    old_schema[key] = schema['singleRoomsDoor1']
            else:
                old_schema[key] = []
        else:
            old_schema[key] = values

    return old_schema


def main(params, dp='.', verbose=False, visualization=False, GAalgo_in_parallell=True):
    algorithmMessage = deepcopy(params['algorithmMessage'])
    params['algorithmMessage'] = [convert_new_form_into_old_for_each_schema(schema_in_new_form) for schema_in_new_form in algorithmMessage]
    inputs4global_layout = _get_inputs_for_global_auto_layout(params)

    _dp = dp
    for i, schema in enumerate(params['algorithmMessage']):
        if i > 2: continue

        sub_dp = os.path.join(_dp, f'schema{i}')
        #     main_zones, desk_orientations4main_zones, passageway_locations4main_zones, \
        #         boundary_against_in_Y_axis4main_zones, boundary_against4main_zones, \
        #             sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, boundary = prepare_inputs_for_layout_with_nothing(schema, boundary_against_in_Y_axis4main_zones, boundary_against4main_zones,
        #                                                                                                                                    dp=sub_dp, visualization=False)
        #                                                                                             # prepare_inputs_ver2(schema, dp=sub_dp, visualization=False)
            
        #     outputs, components = run(main_zones, desk_orientations4main_zones, passageway_locations4main_zones, 
        #                             boundary_against_in_Y_axis4main_zones, boundary_against4main_zones, connect_main_zones_in_general,
        #                                 sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, boundary, 
        #                                 num_of_accompaniment_seats, magnification, dp=sub_dp, verbose=verbose, visualization=visualization,
        #                                 unfold=False)
        #     continue
        
        if schema['non_office_area']:
            input_preparation_func = prepare_inputs_with_reception
        else:
            input_preparation_func = prepare_inputs_without_reception
        main_door, (main_zones, desk_orientations4main_zones, passageway_locations4main_zones, \
            boundary_against_in_Y_axis4main_zones, boundary_against4main_zones, \
                sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, boundary) = input_preparation_func(schema, dp=sub_dp, visualization=visualization)
                                                                                                # prepare_inputs_ver2(schema, dp=sub_dp, visualization=False)
        # continue

        start_time = time.time()
        # _, outputs, components = run(main_door, main_zones, desk_orientations4main_zones, passageway_locations4main_zones, 
        _, components_dict, storage_partition_below_two_col_islands, components_dict_in_form_of_rects = run(main_door, main_zones, desk_orientations4main_zones, passageway_locations4main_zones, 
                                boundary_against_in_Y_axis4main_zones, boundary_against4main_zones, connect_main_zones_in_general,
                                    sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, boundary, 
                                    inputs4global_layout=inputs4global_layout, 
                                    dp=sub_dp, verbose=verbose, visualization=visualization,
                                    turn_on_early_stopping=True,
                                    GAalgo_in_parallell=GAalgo_in_parallell,
                                    unfold=False)
        end_time = time.time()
        runtime = str(datetime.timedelta(seconds=end_time - start_time))
        print(f'runtime: {runtime}')

        outputs = aggregate_components4main_zones(components_dict, storage_partition_below_two_col_islands, global_auto_layout=True)

        if visualization:
            zones = main_zones + sub_zones
            _plot_aggreated_components(components_dict_in_form_of_rects, storage_partition_below_two_col_islands, 
                                        outputs['chairs'], outputs['accompaniment_chairs'],
                                        zones, boundary, main_door, sub_dp,
                                        main_zones=main_zones, sub_zones=sub_zones)
            

        params = _write_out_furnitures(outputs, i, params, gloabal_roation=schema['rotation'])

    return params


def _plot_layout(workspace_pathSegs, layout_pathSegs, dp='.', fp='layout.png', figsize=(10, 8), ax=None):
    def __fill_region(path, color='grey'):
        xs = [v[0] for vertexes in path for v in vertexes]
        ys = [v[1] for vertexes in path for v in vertexes]
        ax.fill(xs, ys, color=color)

    coords = list(chain.from_iterable(layout_pathSegs))
    boundary = envelope(MultiPoint(coords))

    minx, miny, maxx, maxy = boundary.bounds
    if ax is None:
        fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(minx, maxx)
    ax.set_ylim(miny, maxy)

    __fill_region(layout_pathSegs, color='grey')
    __fill_region(workspace_pathSegs, color='blue')

    if not os.path.exists(dp):
        os.makedirs(dp)
    fp = os.path.join(dp, fp)

    plt.legend()
    plt.savefig(fp)
    return ax

__get_edges = lambda path_segs: [[(seg[vertex]['x'], seg[vertex]['y']) for vertex in ['start', 'end']] for seg in path_segs]
__get_region = lambda region_pathSegs: Polygon(list(chain.from_iterable(region_pathSegs)))

def _mock_office_rooms(baseMessage, dp='.'):
    workspace_pathSegs = __get_edges(baseMessage['pathSegs'])

    # room_datas = __get_edges(baseMessage['regionDatas'][0]['corePathInfos'])
    layout_pathSegs = read_json('./tests4L-type_layout/L-type_on_left/schemas.json')['baseMessage']['pathSegs']
    layout_pathSegs = __get_edges(layout_pathSegs)
    _plot_layout(workspace_pathSegs, layout_pathSegs, dp=dp)

    workspace = Polygon(list(chain.from_iterable(workspace_pathSegs)))
    layout = Polygon(list(chain.from_iterable(layout_pathSegs)))
    *_, maxx, maxy = layout.bounds
    publicDoor = (maxx, 0)

    offices = list(difference(layout, workspace).geoms)
    return publicDoor, [list(office.exterior.coords )for office in offices], list(layout.exterior.coords)

def _mock_reception(roomBoundary, dp='.'):
    layout = Polygon(roomBoundary)
    layout_pathSegs = [(start, end) for start, end in zip(layout.exterior.coords, layout.exterior.coords[1:])]

    inner_vertex = __get_inner_vertexes(layout)[0]
    if False:
        _x, _y = inner_vertex
        shifts_in_X_axis = (-2000, 4000)
        shifts_in_Y_axis = (-2000, 4000)
        reception_box = envelope(MultiPoint([Point(x + _x, _y) for x in shifts_in_X_axis] +
                                            [Point(_x, y + _y) for y in shifts_in_Y_axis]))
        empty_zone = difference(envelope(layout), layout)
        reception = difference(reception_box, empty_zone)
    elif False:
        _x, _y = inner_vertex
        reception = envelope(LineString([Point(_x + 5000, _y), 
                                         Point(_x + 12000, _y + 4000)]))
    elif True:
        _x, _y = inner_vertex
        reception = envelope(LineString([Point(_x, _y + 2000),
                                         Point(_x - 5000, _y - 5000)]))

    coords = reception.exterior.coords
    reception_pathSegs = [(start, end) for start, end in zip(coords, coords[1:])]
    _plot_layout(reception_pathSegs, layout_pathSegs, dp=dp)
    

    publicDoor = inner_vertex

    # return publicDoor, list(reception.exterior.coords), list(layout.exterior.coords)
    return publicDoor, list(reception.exterior.coords)
    

def main_for_diff_layouts(params, layout_type='L-Type',
                            dp='.', verbose=False, visualization=False,
                            GAalgo_in_parallell=True):
    algorithmMessage = deepcopy(params['algorithmMessage'])
    params['algorithmMessage'] = [convert_new_form_into_old_for_each_schema(schema_in_new_form) for schema_in_new_form in algorithmMessage]
    inputs4global_layout = _get_inputs_for_global_auto_layout(params)
    
    _dp = dp
    for i, schema in enumerate(params['algorithmMessage']):
        if i > 2: continue
        
        sub_dp = os.path.join(_dp, f'schema{i}')

        # if _dp.endswith('L-type_on_left_with_office_rooms'):
        #     schema['publicDoor'], schema['singleRooms'], schema['roomBoundary'] = _mock_office_rooms(params['baseMessage'], dp=sub_dp)
        #     schema['doorWindowDatas'] = params['baseMessage']['doorWindowDatas']
        # elif _dp.endswith('L-type_on_right_with_office_rooms/prod1'):
        #     schema['publicDoor'], schema['non_office_area'] = _mock_reception(schema['roomBoundary'], dp=sub_dp)


        (boundary, door), (rotations4cutted_zones, boundary_centriod), \
            (rotated_cutted_zones, main_door, rotated_receptions_in_cutted_zones, 
            main_zones, desk_orientations4main_zones, passageway_locations4main_zones, boundary_against_in_Y_axis4main_zones, boundary_against4main_zones, \
            rotated_doors_in_cutted_zones, offices_in_cutted_zones, sub_zones2cutted_zones, main_zones2cutted_zones, 
            sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, boundaries4sub_zones) = prepare_inputs_for_diff_layouts(schema, layout_type=layout_type)
                                                                                                # prepare_inputs_ver2(schema, dp=sub_dp, visualization=False)
        # continue
        _, components_dict, storage_partition_below_two_col_islands, components_dict_in_form_of_rects = run(main_door, main_zones, desk_orientations4main_zones, passageway_locations4main_zones, 
                                boundary_against_in_Y_axis4main_zones, boundary_against4main_zones, connect_main_zones_in_general,
                                    sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, boundary, 
                                    inputs4global_layout=inputs4global_layout, 
                                    turn_on_early_stopping=True,
                                    GAalgo_in_parallell=GAalgo_in_parallell,
                                    dp=sub_dp, verbose=verbose, visualization=visualization,
                                    unfold=False)
         
        rotations4main_zones = [rotations4cutted_zones[main_zones2cutted_zones[zone]] for zone in main_zones]
        components_dict['main_zones'] = rotate_back_components4zones(components_dict['main_zones'], rotations4main_zones, centroid=boundary_centriod)
        rotations4sub_zones = [rotations4cutted_zones[sub_zones2cutted_zones[sub_zone]] for sub_zone in sub_zones]
        if 'sub_zones' in components_dict.keys():
            components_dict['sub_zones'] = rotate_back_components4zones(components_dict['sub_zones'], rotations4sub_zones, centroid=boundary_centriod)
        outputs = aggregate_components4main_zones(components_dict, storage_partition_below_two_col_islands, global_auto_layout=True)


        if visualization:
            components_dict_in_form_of_rects['main_zones'] = rotate_back_components4zones(components_dict_in_form_of_rects['main_zones'],
                                                                                          rotations4main_zones, centroid=boundary_centriod,in_output=False)
            if 'sub_zones' in components_dict_in_form_of_rects.keys():
                components_dict_in_form_of_rects['sub_zones'] = rotate_back_components4zones(components_dict_in_form_of_rects['sub_zones'],
                                                                                            rotations4sub_zones, centroid=boundary_centriod, in_output=False)
            
            main_zones_rotated_back = [_rotate_back_a_rect((zone, None), rotations4cutted_zones[main_zones2cutted_zones[zone]], centroid=boundary_centriod) for i, zone in enumerate(main_zones)]
            sub_zones_rotated_back = [_rotate_back_a_rect((zone, None), rotations4cutted_zones[sub_zones2cutted_zones[zone]], centroid=boundary_centriod) for zone in sub_zones]
            doors_group_rotated_back = [[_rotate_back_door(rotated_door, rotation, centroid=boundary_centriod) for rotated_door in rotated_doors] 
                                     for rotated_doors, rotation in zip(rotated_doors_in_cutted_zones, rotations4cutted_zones)]
            main_door_in_rotated_cutted_zones = [_rotate_back_door(main_door, rotation, boundary_centriod) for rotated_cutted_zone, rotation in zip(rotated_cutted_zones, rotations4cutted_zones)
                                                if rotated_cutted_zone.intersects(main_door)]
            main_door_rotated_back = main_door_in_rotated_cutted_zones[0] if main_door_in_rotated_cutted_zones else main_door
            rotated_receptions_in_cutted_zones = [_adapt_a_zone(poly) if poly else None for poly in rotated_receptions_in_cutted_zones]
            receptions_rotated_back = [_rotate_back_a_rect((zone, None), rotations4cutted_zones[i], centroid=boundary_centriod) if zone else None
                                       for i, zone in enumerate(rotated_receptions_in_cutted_zones)]
            _plot_aggreated_components(components_dict_in_form_of_rects, storage_partition_below_two_col_islands, 
                                        outputs['chairs'], outputs['accompaniment_chairs'],
                                        [], boundary, main_door_rotated_back, sub_dp,
                                        main_zones=main_zones_rotated_back, sub_zones=sub_zones_rotated_back,
                                        offices_group=offices_in_cutted_zones, doors_group=doors_group_rotated_back,
                                        receptions=receptions_rotated_back)

        params = _write_out_furnitures(outputs, i, params, schema['rotation'])

    return params


def _initialize_inputs(deskRelativeMessage, furnitureDatas,
                       models=models, types=types,
                       all_possible_models=['L6', 'L7', 'L9', 'L10', 'GROUP-1']):
    # desk_inputs = {
    #     'persons': deskRelativeMessage['seat'],
    #     'accompanyment_seats': deskRelativeMessage['stepNumber']
    # }
    desk_inputs = {'persons' if key == 'seat' else
                   'accompanyment_seats' if key == 'stepNumber' else
                   key: value for key, value in deskRelativeMessage.items()}

    _furnitures = {item['modelId']: item['quantities'] for item in furnitureDatas}
    _furniture_inputs = {modelId: _furnitures[modelId] if modelId in _furnitures.keys() else 0 for modelId in
                         all_possible_models}
    models2types = dict(zip(models, types))
    furniture_inputs = {'printer_sets' if modelId == 'GROUP-1' else models2types[modelId]: num for modelId, num in
                        _furniture_inputs.items()}
    inputs = {**desk_inputs, **furniture_inputs}
    return inputs


def main_for_local_layout(params, dp=None, verbose=False, visualization=False):
    inputs = _initialize_inputs(params['userInput']['deskRelativeMessage'], params['userInput']['furnitureDatas'])

    rotation, main_door, (boundary_against_in_Y_axis4main_zone, boundary_against4main_zone), region = identify_region(
        params['baseMessage'])

    boundary_against_in_Y_axis4main_zones, boundary_against4main_zones = [boundary_against_in_Y_axis4main_zone], [
        boundary_against4main_zone]
    main_zones, desk_orientations4main_zones, passageway_locations4main_zones = [_adapt_a_zone(region)], [False], [
        'down']
    sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones = [], [], []
    boundary = region

    if 'persons' in inputs.keys():
        turn_on_early_stopping = False
    else:
        turn_on_early_stopping = True
    nums_outputed, outputs, components = run(main_door, main_zones, desk_orientations4main_zones,
                                             passageway_locations4main_zones,
                                             boundary_against_in_Y_axis4main_zones, boundary_against4main_zones,
                                             connect_main_zones_in_general,
                                             sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones,
                                             boundary,
                                             inputs4local_layout=inputs,
                                             turn_on_early_stopping=turn_on_early_stopping,
                                             dp=dp, verbose=verbose, visualization=visualization, unfold=False)

    _inputs = {key: num for key, num in inputs.items() if key not in ['height', 'width', 'islandSpaceing']}
    satisfied = all(
        _num <= nums_outputed[comp] if comp in nums_outputed.keys() else False for comp, _num in _inputs.items())

    furnitureDatas = add_ids(outputs)
    global_furnitureDatas = [_rotate_back(item, -math.radians(rotation)) for item in furnitureDatas]

    i = 0
    params['algorithmMessage'][i]['components4visualization'] = {
        'boundary': _adapt_a_zone(region),
        'main_zones': main_zones,
        'sub_zones': sub_zones,
        'components': components,
        'chairs': outputs['chairs']
    }
    if satisfied:
        params['outPutMessage'][i]['furnitureDatas'].extend(global_furnitureDatas)

    return params

# def main(params, dp=None, verbose=False, visualization=False):
#     magnification = {
#         'locker': 1,
#         'cabinet': 1.5
#     }
#
#     if not dp:
#         dp = os.path.dirname(os.path.abspath(__file__))
#         dp = os.path.join(dp, 'data')
#     _dp = dp
#     for i, schema in enumerate(params['algorithmMessage']):
#         try:
#             sub_dp = os.path.join(_dp, f'schema{i}')
#             main_zones, desk_orientations4main_zones, passageway_locations4main_zones, boundary_against4main_zones, \
#                     sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, boundary = prepare_inputs_ver2(schema, dp=sub_dp, visualization=visualization)
#
#             outputs, components = run(main_zones, desk_orientations4main_zones, passageway_locations4main_zones, boundary_against4main_zones, None,
#                         sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, boundary, magnification, dp=sub_dp, verbose=verbose, visualization=visualization)
#
#             furnitureDatas = add_ids(outputs)
#
#             global_furnitureDatas = [_rotate_back(item, *schema['rotation']) for item in furnitureDatas]
#             params['outPutMessage'][i]['furnitureDatas'].extend(global_furnitureDatas)
#
#             params['algorithmMessage'][i]['components4visualization'] = {
#                 'boundary': boundary,
#                 'main_zones': main_zones,
#                 'sub_zones': sub_zones,
#                 'components': components,
#                 'chairs': outputs['chairs']
#         }
#         except Exception as e:
#             print('error', e)
#
#     return params


# if __name__ == '__main__':
#     magnification = {
#         'locker': 1,
#         'cabinet': 1.5
#     }

#     if True:
#         verbose, visualization = True, True

#         filename='schema.json'
#         _dir, _sub_dir = 'tests', 'test3'
#         # _dir, _sub_dir = 'tests', 'error1'
#         # _dir, _sub_dir = 'tests', 'error4_1'
#         # filename = f'{_sub_dir}.json'

#         dp = os.path.join(os.path.dirname(os.path.abspath(__file__)), _dir)
#         test_dp = os.path.join(dp, _sub_dir)
#         schemas = read_json(filename, dp=test_dp)

#         # new_dp = os.path.join(dp, 'reresults')
#         new_dp = test_dp
#         # main(schemas, dp=new_dp, verbose=verbose, visualization=visualization)

#         # schema = schemas['algorithmMessage'][0]
#         schema = schemas
#         main_zones, desk_orientations4main_zones, passageway_locations4main_zones, boundary_against4main_zones, \
#                     sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, boundary = prepare_inputs_ver2(schema, dp=test_dp)

#     elif False:
#         region_dict, boundary = get_inputs()
#         adapted_region_dict = adapt_inputs(region_dict)

#         main_zones, sub_zones = adapted_region_dict['main_zones'], adapted_region_dict['sub_zones']
#         boundary_against4main_zones = [('window' if i == 0 else 'two_col_islands', 'wall') for i in enumerate(main_zones)]
#     else:
#         boundary_against4main_zones = [('window', 'wall')] * len(main_zones)


#     # import os
#     # dp = os.path.dirname(os.path.abspath(__file__))
#     # dp = os.path.join(dp, 'data_ver3')
#     # if not os.path.exists(dp):
#     #     os.makedirs(dp)

#     outputs = run(main_zones, desk_orientations4main_zones, passageway_locations4main_zones, boundary_against4main_zones, None,
#                     sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, boundary, magnification, dp=test_dp)

#     furnitureDatas = add_ids(outputs)


