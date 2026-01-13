import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
import matplotlib.colors as mcolors

from shapely import difference, envelope
from shapely import MultiPoint, Point

from pathlib import Path
import os

def _plot_rectangles(ax, min_coords, rectangles, spacings=None, color='blue', fontsize='xx-small', offset=1/4):
    for i, (min_xy, (x, y)) in enumerate(zip(min_coords, rectangles)):
        ax.add_patch(Rectangle(xy=min_xy, width=x, height=y, fill=None, edgecolor=color, alpha=0.5))

        table_half_x, table_half_y = min_xy[0] + x/2,  min_xy[1] + y/2
        fontdict = dict(fontsize=fontsize, color=color)

def plot_resulting_layout(RECTs_dict, zones, boundary, dp=None, fp='resulting_layout.png', figsize=(8, 12)):
    xlim, ylim = boundary

    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(0, xlim)
    ax.set_ylim(0, ylim)

    for min_xy, (x, y) in zones:
        ax.add_patch(Rectangle(xy=min_xy, width=x, height=y, fill=None, edgecolor='black', alpha=0.5))

    for partition, RECTs_list in RECTs_dict.items():
        for RECTs in RECTs_list:
            for RECT, color in zip(RECTs, mcolors.TABLEAU_COLORS):
                if not RECT: continue
                min_xy, (X, Y) = RECT
                ax.add_patch(Rectangle(xy=min_xy, width=X, height=Y, fill=None, edgecolor=color, alpha=0.5))

    if not dp:
        dp = Path(__file__).resolve().parents[0]
    fp = os.path.join(dp, fp)
    plt.savefig(fp)



def plot_component_placements(component_plmts, zones, boundary, main_door=None,
                              main_zones=[], sub_zones=[], offices_group=[], doors_group=[], receptions=[],
                              dp=None, fp='component_placments.png', figsize=(10, 8)):
    minx, miny, maxx, maxy = boundary.bounds
    _boundary = (maxx - minx, maxy - miny)


    (minx, miny), (xlim, ylim) = boundary

    fig, ax = plt.subplots(figsize=figsize)
    # ax.set_xlim(0, xlim)
    # ax.set_ylim(0, ylim)
    ax.set_xlim(minx, minx + xlim)
    ax.set_ylim(miny, miny + ylim)

    box = envelope(MultiPoint(boundary.exterior.coords))
    nonexistance = difference(box, boundary)
    xs = [x for x, _ in nonexistance.exterior.coords]
    ys = [y for _, y in nonexistance.exterior.coords]
    ax.fill(xs, ys, 'grey')

    def _plot_zones(zones, color='grey', ax=ax):
        for rect in zones:
            if rect is None: continue
            min_xy, (x, y) = rect
            ax.add_patch(Rectangle(xy=min_xy, width=x, height=y, fill=True, color=color, alpha=0.5))

    _plot_zones(main_zones, color='blue')
    _plot_zones(sub_zones, color='orange')

    _plot_zones(receptions, color='black')
    # _plot_zones(offices_group, color='grey')
    for offices, color in zip(offices_group, ['gray', 'brown']):
        offices_in_form_of_rectangle = [] 
        for office in offices:
            *min_xy, maxx, maxy = office.bounds
            x, y = min_xy
            X = maxx - x
            Y = maxy - y
            offices_in_form_of_rectangle.append((min_xy, (X, Y)))
        _plot_zones(offices_in_form_of_rectangle, color=color)


    for doors, color in zip(doors_group, mcolors.TABLEAU_COLORS):
        for door in doors:
            # circle = Circle((door.x, door.y), radius=1000, color=color, alpha=0.5)
            # ax.add_patch(circle)
            minx, miny, maxx, maxy = door.bounds
            X = maxx - minx
            Y = maxy - miny
            ax.add_patch(Rectangle(xy=(minx-250, miny-250), width=X + 250, height=Y + 250, fill=True, edgecolor=color, alpha=0.5))
    

    # for partition, RECTs_list in RECTs_dict.items():
    #     for RECTs in RECTs_list:
    #         for RECT, color in zip(RECTs, mcolors.TABLEAU_COLORS):
    #             if not RECT: continue
    #             min_xy, (X, Y) = RECT
    #             ax.add_patch(Rectangle(xy=min_xy, width=X, height=Y, fill=None, edgecolor='black', alpha=0.5))

    
    for (comp, plmts), color in zip(component_plmts.items(), mcolors.TABLEAU_COLORS):
        if not plmts: continue
        for (min_xy, (X, Y)), _ in plmts:
            ax.add_patch(Rectangle(xy=min_xy, width=X, height=Y, fill=None, edgecolor=color, alpha=0.5))

    # for (comp, plmts), color in zip(component_plmts.items(), mcolors.TABLEAU_COLORS):
    #     if comp.endswith('chairs') or not plmts: continue

    #     for plmt in plmts:
    #         x, y = plmt['center']['x'], plmt['center']['y']
    #         X, Y = plmt['width'], plmt['height']
    #         min_xy = (x - X/2, y - Y/2)
    #         ax.add_patch(Rectangle(xy=min_xy, width=X, height=Y, fill=None, edgecolor=color, alpha=0.5))

    if main_door:
        circle = Circle((main_door.x, main_door.y), radius=1600, color='red', alpha=0.5)
        ax.add_patch(circle)

    if not dp:
        dp = Path(__file__).resolve().parents[0]

    if not os.path.exists(dp):
        os.makedirs(dp)
    fp = os.path.join(dp, fp)

    plt.legend()
    plt.savefig(fp)
    return ax


def plot_chairs(ax, chairs, dp=None, fp='chair_placements.png'):
    for chair in chairs:
        circle = Circle((chair['center']['x'], chair['center']['y']), radius=700/2, facecolor='blue', alpha=0.5)
        ax.add_patch(circle)

    if not dp:
        dp = Path(__file__).resolve().parents[0]
    if not os.path.exists(dp):
        os.makedirs(dp)
    fp = os.path.join(dp, fp)

    plt.legend()
    plt.savefig(fp)



def plot(zones, boundary, fp='layout.png', figsize=(8, 12)):
    xlim, ylim = boundary

    fig, ax = plt.subplots(figsize)
    ax.set_xlim(0, xlim)
    ax.set_ylim(0, ylim)

    for min_xy, (x, y) in zones:
        ax.add_patch(Rectangle(xy=min_xy, width=x, height=y, fill=None, edgecolor='blue', alpha=0.5))

    dp = Path(__file__).resolve().parents[0]
    fp = os.path.join(dp, fp)
    plt.savefig(fp)

