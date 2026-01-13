origin = (0, 0)
xlim = 100000 / 2
ylim = 200000 / 2
boundary = (xlim, ylim)

cut_point = (0.45 * xlim, 0.65 * ylim)
# cut_point = (0.45 * xlim, 0.6 * ylim)
main_zones = [
    (origin, (cut_point[0], ylim)),
    (cut_point, (xlim - cut_point[0], ylim - cut_point[1]))
]

subzone_width_list = [0.1 * xlim, 0.15 * ylim]
sub_zones = [
    ((cut_point[0], 0), (subzone_width_list[0], cut_point[1])),
    ((cut_point[0] + subzone_width_list[0], cut_point[1] - subzone_width_list[1]), 
     (0.6 * (xlim - cut_point[0] - subzone_width_list[0]), subzone_width_list[1]))
]

desk_orientations4main_zones = [        # parallel to x axis: 1
    1,
    0
]
storage_orientations4sub_zones = [      # parallel to x axis: 1
    1,
    0
]

passageway_locations4main_zones = [
    'right',
    'down'
]
wall_locations4sub_zones = [
    'right',
    'down'
]

from .configs import sizes
printers, walls_to_put_printers = [3, 2], ['y', 'x']
size = sizes['printer'][0]
splited_sub_zones = []
storage_orientations4splited_sub_zones = []
for sub_zone, storage_orientation, num_of_printers, wall in zip(sub_zones, storage_orientations4sub_zones, printers, walls_to_put_printers):
    origin, RECT = sub_zone
    length = RECT[0] if wall == 'x' else RECT[1]
    gap = (length - size) / (num_of_printers - 1)
    interval = gap - size

    x, y = origin
    origins = [(x + size + gap * i, y) for i in range(num_of_printers-1)] if wall == 'x' else \
                [(x, y + size+ gap * i) for i in range(num_of_printers-1)]
    X, Y = RECT
    rects = [(interval, Y)] * (num_of_printers-1) if wall == 'x' else [(X, interval)] * (num_of_printers-1)
    
    splited_sub_zones += [(orgn, rect) for orgn, rect in zip(origins, rects)]
    storage_orientations4splited_sub_zones += [storage_orientation] * num_of_printers
# sub_zones = splited_sub_zones
# storage_orientations4sub_zones = storage_orientations4splited_sub_zones


# def reserve_space_for_printers(zones, walls_to_put_printers, size=sizes['printer'][0]):
#     reduced_zones = []
#     for zone, wall in zip(zones, walls_to_put_printers):
#         origin, RECT = zone
#         X, Y = RECT
#         if wall == 'x': 
#             reduced_RECT = (X, Y - size) 
#         else:
#             reduced_RECT = (X - size, Y)
#             x, y = origin
#             origin = (x + size, y)
#         reduced_zones.append((origin, reduced_RECT))
#     return reduced_zones

# sub_zones = reserve_space_for_printers(sub_zones, ['y', 'x'])
# main_zones = reserve_space_for_printers(main_zones, ['x', 'y'])

if __name__ == '__main__':
    from plot import plot

    plot(main_zones + sub_zones, boundary)

