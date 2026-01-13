from shapely.geometry import Point, GeometryCollection, LineString
from shapely import envelope
import os
from copy import deepcopy

from split_zones import connect_office_rooms, plot
from main import write_json, read_json


def _generate_test1_data(boundary, reception, door, offices):
    _minx, _miny, _maxx, _maxy = boundary.bounds
    _extended_offices = [
        envelope(GeometryCollection([offices[0], Point(_minx, _miny)])),
        envelope(GeometryCollection([offices[1], Point(_maxx, _maxy)]))
    ]
    size = len(_extended_offices)
    for i in range(size):
        minx, miny, maxx, maxy = _extended_offices[i].bounds
        if i == 0:
            _additional_room = envelope(GeometryCollection([Point(_minx, maxy), Point(3000, 20000)]))
        elif i == 1:
            _additional_room = envelope(GeometryCollection([Point(minx, _maxy), Point(30000, _maxy - 4000)]))
        _extended_offices.append(_additional_room)
    offices = _extended_offices
    return offices


def _generate_test2_data(boundary, reception, door, offices):
    _extended_offices = [
        envelope(GeometryCollection([offices[0], Point(10000, 0)]))
    ]

    _minx, _miny, _maxx, _maxy = boundary.bounds
    _additional_offices = [
        envelope(LineString([Point(*boundary.bounds[:2]), Point(5000, 25000)])),
        envelope(LineString([Point(_minx, _maxy), Point(35000, _maxy - 5000)])),
        envelope(LineString([Point(reception.bounds[2], 5000), Point(offices[1].bounds[:2])]))
    ]
    offices = _extended_offices + _additional_offices + [offices[1]]
    return offices


def _generate_test3_data(boundary, reception , door, offices):
    _minx, _, _maxx, *_ = boundary.bounds

    minx, *_, maxy = offices[0].bounds
    x = 10000
    _additional_offices = [
        envelope(LineString([Point(x, 0), Point(minx, maxy)])),
        envelope(LineString([Point(*boundary.bounds[:2]), Point(x, maxy)])),
        envelope(LineString([Point(_minx, maxy), Point(5000, 30000)]))
    ]

    minx, *_, maxy = offices[1].bounds
    _additional_offices += [
        envelope(LineString([Point(minx, maxy), Point(_maxx, 35000)])),
        envelope(LineString([Point(45000, 35000), Point(*boundary.bounds[-2:])]))
    ]

    minx, miny, maxx, maxy = reception.bounds
    _additional_offices += [
        envelope(LineString([Point(minx, maxy), Point(minx + 3000, maxy + 3000)])),
        envelope(LineString([Point(minx + 3000, maxy), Point(maxx + 2000, maxy + 3000)])),
        envelope(LineString([Point(maxx, maxy - 5000), Point(maxx + 5000, maxy)])),
        envelope(LineString([Point(maxx, miny + 4000), Point(maxx + 8000, maxy - 5000)])),
        envelope(LineString([Point(maxx, miny + 4000), Point(*offices[1].bounds[:2])]))
    ]
    offices += _additional_offices
    return offices


def generate_test_data(gen_func, schema, dp=None):
    boundary, reception, door, offices = connect_office_rooms(schema)
    offices = offices[::-1]
    
    modified_offices = gen_func(boundary, reception, door, offices)
    plot([reception] + modified_offices, door, boundary, dp=dp)

    schema['singleRooms'] = [rectangle.exterior.coords[:] for rectangle in modified_offices]
    write_json(schema, 'schema.json', dp=dp)




if __name__ == '__main__':
    print('Generating test data...')
    dp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tests')

    test_dp = os.path.join(dp, 'test0')
    schemas = read_json(filename='schemas.json', dp=test_dp)
    schema = schemas['algorithmMessage'][0]

    tests, gen_funcs = [f'test{i}' for i in range(1, 4)], [
        _generate_test1_data, _generate_test2_data, _generate_test3_data
    ]
    i = 2
    for test, gen_func in zip(tests[i:], gen_funcs[i:]):
        sub_dp = os.path.join(dp, test)
        schema = deepcopy(schema)
        generate_test_data(gen_func, schema, dp=sub_dp)