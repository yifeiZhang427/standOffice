from deap import creator, tools, base, algorithms
from shapely import envelope
from shapely import LineString, Point

import random
import numpy as np
from copy import deepcopy
import math
import multiprocessing

from .model import calcu_bounds_for_individual, _generate_an_individual, _evaluate, bound
from ._evaluate_local_layout import _evaluate_local_layout, get_outputs
from ._eaSimple_with_early_stopping import _eaSimple_with_early_stopping

from rotate_back_new_by_yifei import rotate_back_new

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))
from general.plot import plot_resulting_layout, plot_component_placements, plot_chairs
from general.configs import sizes



def output_components4zone(aggregated_components_dict, with_main_zones_reflected=False,
                            user_desk=sizes['desk']):
    def _output(rect, comp, user_desk=user_desk):
        output = {}
        ((x, y), (X, Y)), rotation = rect
        output['center'] = {
            'x': (x + X / 2),
            'y': (y + Y / 2)
        }
        # ouput['rotation'] = False if X > Y else True
        if rotation is None:
            output['rotation'] = 0 if X > Y else math.radians(90)
        else:
            output['rotation'] = math.radians(rotation)

        if comp.startswith('desks_'):
            l, w = user_desk
            unit = int(Y / l)
            output['width'], output['height'] = (unit * l, w * 2)
        else:
            output['width'], output['height'] = (max(X, Y), min(X, Y))
        return output
    

    outputs = {comp: [_output(rect, comp) for rect in rects] for comp, rects in aggregated_components_dict.items()}

    
    def _get_chairs(desk, in_unit, mixed=False, with_main_zones_reflected=False, sizes=sizes):
        l, w = sizes['chair']

        def __get_chairs_in_desk_unit(desk, mixed, with_main_zones_reflected=with_main_zones_reflected):
            x, y = desk['center']['x'], desk['center']['y']
            if desk['rotation']:
                signs, rotations = [-1, 1], [90, 270]
                centers = [(x + sign * (desk['height'] / 2 + w / 2), y) for sign in signs]
            else:
                signs, rotations = [-1, 1], [180, 0]
                centers = [(x, y + sign * (desk['height'] / 2 + w / 2)) for sign in signs]
            chairs = [{
                'center': {'x': x, 'y': y},
                'rotation': math.radians(rotation),
                'width': l,
                'height': w
            } for (x, y), rotation in zip(centers, rotations)]

            if mixed:
                if desk['rotation']:
                    if with_main_zones_reflected:
                        del chairs[1]
                    else:
                        del chairs[0]
                else:
                    if with_main_zones_reflected:
                        del chairs[0]
                    else:
                        del chairs[1]

            return chairs

        if in_unit == 1:
            chairs = __get_chairs_in_desk_unit(desk, mixed)
        elif in_unit == 3:
            x, y = desk['center']['x'], desk['center']['y']
            l_in_unit = desk['width'] / in_unit
            _desk = deepcopy(desk)
            _desk['width'] = l_in_unit
            desks = [_desk]
            # + [(x, y + sign * l_in_unit) if desk['rotation'] else (x + sign * l_in_unit, y) for sign in [-1, 1]]
            for sign in [-1, 1]:
                __desk = deepcopy(_desk)
                center = (x, y + sign * l_in_unit) if desk['rotation'] else (x + sign * l_in_unit, y)
                __desk['center'] = {
                    'x': center[0],
                    'y': center[1]
                }
                desks.append(__desk)

            chairs = []
            for desk in desks:
                chairs += __get_chairs_in_desk_unit(desk, mixed)
        return chairs

    def _get_chairs_for_each_accompaniment_seat(desk, sizes=sizes):
        l, w = sizes['chair']

        x, y = desk['center']['x'], desk['center']['y']
        signs, rotations = [1, -1], [0, 180]
        centers = [(x, y + sign * (desk['height'] / 2 + w / 2)) for sign in signs]

        rotations += [rotations[-1]]
        x, y = centers[-1]
        del centers[-1]
        centers += [(x + sign * w / 2, y) for sign in signs]

        chairs = [{
            'center': {'x': x, 'y': y},
            'rotation': math.radians(rotation),
            'width': l,
            'height': w
        } for (x, y), rotation in zip(centers, rotations)]
        return chairs[:1], chairs[1:]

    outputs['chairs'] = []
    outputs['accompaniment_chairs'] = []
    for comp, comp_list in outputs.items():
        if comp == 'accompaniment_seat_in_unit1':
            for desk in comp_list:
                chairs, accompaniment_chairs = _get_chairs_for_each_accompaniment_seat(desk)
                outputs['chairs'] += chairs
                outputs['accompaniment_chairs'] += accompaniment_chairs
        elif 'desk' in comp:
            in_unit = int(comp.split('in_unit')[-1])
            mixed = True if comp.startswith('mixed') else False
            for desk in comp_list:
                outputs['chairs'] += _get_chairs(desk, in_unit=in_unit, mixed=mixed,
                                                 with_main_zones_reflected=with_main_zones_reflected)

    return outputs


def _mutUniformInt(low, up, individual, indpb=0.2):
    size = len(individual)
    for i, xl, xu in zip(range(size), low, up):
        if random.random() < indpb:
            individual[i] = random.randint(xl, xu)

    return individual,


def _initialize_ga(main_door, boundary, main_zones, desk_orientations4main_zones, passageway_locations4main_zones,
                   boundary_against_in_Y_axis4main_zones, boundary_against4main_zones, connect_main_zones,
                   sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones,
                   inputs4global_layout=None,
                   inputs4local_layout=None, unfold=False):
    walls4main_zones, upbounds, lows, ups = calcu_bounds_for_individual(main_zones, desk_orientations4main_zones,
                                                                        sub_zones,
                                                                        boundary_against_in_Y_axis4main_zones,
                                                                        boundary_against4main_zones,
                                                                        inputs4global_layout=inputs4global_layout,
                                                                        inputs4local_layout=inputs4local_layout)

    if inputs4local_layout:
        _inputs4local_layout = {key: value for key, value in inputs4local_layout.items() if
                                key not in ['width', 'height']}
        size = len(_inputs4local_layout.items()) + 8 + len(sub_zones) * 2 * 3 + sum(
            len(walls) for walls in walls4main_zones) * 2 * 3
    else:
        # size =  8 + len(sub_zones)*2 * 3 + len(main_zones)*3 * 2 * 3 + len(main_zones) + len(main_zones) + 3 + 1 + 1 + 1 + 1 + 2
        # len(main_zones) * 2
        size = 14 + 1 + len(sub_zones) * 2 * 3 + len(main_zones) * (1 + 1) + sum(
            len(walls) for walls in walls4main_zones) * 2 * 3 + 2
        # + 1 + 2

    weights = [-1] * size
    creator.create('FitnessMin', base.Fitness, weights=weights)
    creator.create('Individual', list, fitness=creator.FitnessMin)

    toolbox = base.Toolbox()
    toolbox.register('individual', _generate_an_individual, creator.Individual, lows, ups)
    toolbox.register('population', tools.initRepeat, list, toolbox.individual)
    if inputs4local_layout:
        toolbox.register('evaluate', _evaluate_local_layout, main_door, boundary, upbounds, main_zones,
                         desk_orientations4main_zones, passageway_locations4main_zones,
                         walls4main_zones, boundary_against_in_Y_axis4main_zones, boundary_against4main_zones,
                         connect_main_zones,
                         sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones,
                         unfold=unfold, inputs4local_layout=inputs4local_layout)
    else:
        toolbox.register('evaluate', _evaluate, main_door, boundary, upbounds, main_zones, desk_orientations4main_zones,
                         passageway_locations4main_zones,
                         walls4main_zones, boundary_against_in_Y_axis4main_zones, boundary_against4main_zones,
                         connect_main_zones,
                         sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones,
                         unfold=unfold, inputs4global_layout=inputs4global_layout)
    toolbox.register('mate', tools.cxUniform, indpb=0.7)
    toolbox.register('mutate', _mutUniformInt, lows, ups, indpb=0.2)
    toolbox.register('select', tools.selTournament, tournsize=3)
    return toolbox, upbounds, walls4main_zones


def generate_a_layout_via_ga(main_door, boundary, main_zones, desk_orientations4main_zones,
                             passageway_locations4main_zones,
                             boundary_against_in_Y_axis4main_zones, boundary_against4main_zones, connect_main_zones,
                             sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones,
                             inputs4global_layout=None,
                             inputs4local_layout=None, unfold=False,
                             n=300, nsteps=1000, verbose=True,
                             GAalgo_in_parallell=False,
                             turn_on_early_stopping=True):
    #  n=500, nsteps=2000):
    toolbox, upbounds, walls4main_zones = _initialize_ga(main_door, boundary, main_zones, desk_orientations4main_zones,
                                                         passageway_locations4main_zones,
                                                         boundary_against_in_Y_axis4main_zones,
                                                         boundary_against4main_zones, connect_main_zones,
                                                         sub_zones, storage_orientations4sub_zones,
                                                         wall_locations4sub_zones,
                                                         inputs4global_layout=inputs4global_layout,
                                                         inputs4local_layout=inputs4local_layout, unfold=unfold)

    pop = toolbox.population(n=n)
    hof = tools.HallOfFame(1)
    stats = tools.Statistics(lambda ind: ind.fitness.values
                             )
    stats.register("avg", np.mean)
    stats.register("std", np.std)
    stats.register("min", np.min)
    stats.register("max", np.max)

    # algorithms.eaSimple(pop, toolbox, 0.7, 0.2, nsteps, stats=stats,
    #                     halloffame=hof, verbose=verbose)

    if GAalgo_in_parallell:
        pool = multiprocessing.Pool(processes=4)
        toolbox.register("map", pool.map)

    if turn_on_early_stopping:
        _eaSimple_with_early_stopping(pop, toolbox, 0.7, 0.2, nsteps, stats=stats,
                                      halloffame=hof, verbose=verbose)
    else:
        algorithms.eaSimple(pop, toolbox, 0.7, 0.2, nsteps, stats=stats,
                            halloffame=hof, verbose=verbose)

    if GAalgo_in_parallell:
        pool.close()

    solution = hof[0]
    return solution, upbounds, walls4main_zones


def run(main_door, main_zones, desk_orientations4main_zones, passageway_locations4main_zones,
        boundary_against_in_Y_axis4main_zones, boundary_against4main_zones, connect_main_zones,
        sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, boundary,
        inputs4global_layout=None,
        inputs4local_layout=None,
        GAalgo_in_parallell=True,
        turn_on_early_stopping=True,
        unfold=False, dp=None, verbose=True, visualization=True):
    solution, upbounds, walls4main_zones = generate_a_layout_via_ga(main_door, boundary, main_zones,
                                                                    desk_orientations4main_zones,
                                                                    passageway_locations4main_zones,
                                                                    boundary_against_in_Y_axis4main_zones,
                                                                    boundary_against4main_zones, connect_main_zones,
                                                                    sub_zones, storage_orientations4sub_zones,
                                                                    wall_locations4sub_zones,
                                                                    inputs4global_layout=inputs4global_layout,
                                                                    inputs4local_layout=inputs4local_layout,
                                                                    GAalgo_in_parallell=GAalgo_in_parallell,
                                                                    turn_on_early_stopping=turn_on_early_stopping,
                                                                    unfold=unfold, verbose=verbose)

    unfold = True
    total_num_of_low_cabinets, total_num_of_small_lockers, \
    with_main_zones_reflected, penalty4island_connectivity, \
    (storage_partition_below_two_col_islands, components_dict, rectangles_dict, RECTs_dict,
    # (aggregated_components_dict, aggregated_rectangles_dict, RECTs_dict,
    # islands, printer_sets, _islands2printer_sets, _grouped_islands,
    gaps_of_plmts4walls_in_main_zones, num_of_printer_sets_near_walls4sub_zones, num_of_printer_sets_near_walls4main_zones, 
    total_overbounds_of_parallel2x4storage, total_overbounds_of_storage, total_overbounds_of_printer_sets,
    assigned_num_of_accompaniment_seats_list, total_insufficiency_of_accompaniment_seats, total_bound_in_accompaniment_seats_without_islands,
    num_of_islands4storage_list, overbounds_within_main_zones, overbounds_within_sub_zones, total_overbounds_of_high_cabinets_near_wall, num_of_persons, 
    indexes), (penalties_in_order_of_priority, storage_assigned_sofar, required_storage, _priorities, high_storage_plmts, incremental_storages) = \
        bound(main_door, boundary, upbounds, main_zones, desk_orientations4main_zones, passageway_locations4main_zones, 
            walls4main_zones, boundary_against_in_Y_axis4main_zones, boundary_against4main_zones, connect_main_zones,
            sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, solution, 
            unfold=unfold,
            inputs4global_layout=inputs4global_layout, 
            inputs4local_layout=inputs4local_layout)    
    

    inputs = inputs4global_layout if inputs4global_layout else inputs4local_layout
    user_desk = (inputs['tableWidth'], inputs['tableHeight'])

    components_dict_in_form_of_rects = deepcopy(components_dict)
    components_dict4output = {zone_key: [output_components4zone(components_dict, with_main_zones_reflected, 
                                                                user_desk=user_desk) for components_dict in components_dict_list4zone] for zone_key, components_dict_list4zone in components_dict.items()}

    
    if inputs4local_layout:
        nums_outputed = get_outputs(num_of_printer_sets_near_walls4main_zones, num_of_printer_sets_near_walls4sub_zones,
                                    assigned_num_of_accompaniment_seats_list,
                                    total_num_of_small_lockers, total_num_of_low_cabinets,
                                    high_storage_plmts,
                                    num_of_persons)

        _evaluate_local_layout(main_door, boundary, upbounds, main_zones, desk_orientations4main_zones,
                               passageway_locations4main_zones,
                               walls4main_zones, boundary_against_in_Y_axis4main_zones, boundary_against4main_zones,
                               connect_main_zones,
                               sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, solution,
                               unfold=unfold, inputs4local_layout=inputs4local_layout)

    else:
        nums_outputed = None
        _evaluate(main_door, boundary, upbounds, main_zones, desk_orientations4main_zones,
                  passageway_locations4main_zones,
                  walls4main_zones, boundary_against_in_Y_axis4main_zones, boundary_against4main_zones,
                  connect_main_zones,
                  sub_zones, storage_orientations4sub_zones, wall_locations4sub_zones, solution,
                  unfold=unfold,
                  inputs4global_layout=inputs4global_layout)

        # print(f'num_of_persons: {num_of_persons}')
        # print(f'CabinetMagnification: {inputs4global_layout['CabinetMagnification']}, fileCabinetFm: {inputs4global_layout['fileCabinetFm']}')
        # print(f'required_storage: {required_storage}')
        # print(f'storage_assigned_sofar: {storage_assigned_sofar}')
    return nums_outputed, components_dict4output, storage_partition_below_two_col_islands, components_dict_in_form_of_rects

