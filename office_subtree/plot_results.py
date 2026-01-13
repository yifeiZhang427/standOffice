import os

from general.plot import *
from main import read_json


def plot_results(results, dp=None):
    for i, schema in enumerate(results['algorithmMessage']):
        result = schema['components4visualization']

        sub_dp = os.path.join(dp, f'schema{i}')
        if not os.path.exists(sub_dp):
            os.makedirs(sub_dp)
        ax = plot_component_placements(result['components'],{}, result['main_zones'] + result['sub_zones'], result['boundary'], dp=sub_dp)

        plot_chairs(ax, result['chairs'], dp=sub_dp)

if __name__ == '__main__':
    dp = os.path.dirname(os.path.abspath(__file__))
    # dp = os.path.join(dp, 'tests', 'test1')
    # dp = os.path.join(dp, 'tests', 'test0')
    # dp = os.path.join(dp, 'tests', 'test_online0')
    # dp = os.path.join(dp, 'tests', 'test1')
    # dp = os.path.join(dp, 'tests', 'dev1')
    dp = os.path.join(dp, 'tests', 'layout_with_nothing')
    # dp = os.path.join(dp, 'tests', 'layout_with_only_offices')
    # dp = os.path.join(dp, 'tests', 'layout_with_reception_and_offices')


    # dp = os.path.join(dp, 'tests4local_layout', 'dev')
    results = read_json('schemas_outputed.json', dp=dp)
    plot_results(results, dp=dp)