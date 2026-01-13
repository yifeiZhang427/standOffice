# reminder: this information is collected from an upper triangle matrix

spacing = {}


spacing_against_components = {}
# note: 
#   - rows (of subjects) * cols (against_): both in order of (longside, shortside) + e.g., (longside(with closed door)) for storage;
#     - rows: (longside, shortside) + (chair opposite);
#     - cols: (longside, shortside) + (longside(with closed door));
#   - 'storage': representing both high cabinet and big locker;
spacing_against_components['desk'] = {
    'against_desk': [
        [1500, None, 1200],
        [1200, 800, 0],
        [None, None, None]
    ],
    'against_accompany_seat': [
        [None, 1200],
        [1200,  None]
    ],
    'against_small_locker': [
        [1200, 1200, 1200],
        [1100, None, 0],
        [1100, 800, 0]
    ],
    'against_low_cabinet': [
        [1200, 1200, 1200],
        [1100, None, 0],
        [1100, 800, 0]
    ],
    'against_storage': [
        [1200, 1200, None],
        [1100, 800, None],      # to support non-existing combinations of placements in temporary
        [1100, 800, None]
    ],
    'against_printer_set': [
        [1500, 1200, None],
        [1100, None, None],
        [1100, None, None]
    ]
}

spacing_against_components['accompany_seat'] = {
    'against_accompany_seat': [
        [None, None],
        [None, 800]
    ],
    'against_small_locker': [
        [None, None, None],
        [1100, 800, 800]
    ],
    'against_low_cabinet': [
        [None, None, None],
        [1100, 800, 0]
    ],
    'against_storage': [
        [1100, 1100, None],     # to support non-existing combination of placements in temporary
        # [None, None, None],
        [1100, None, None]
    ],
    'against_printer_set': [
        [1100, 1100, None],     # to support non-existing combinations of placements in temporary
        # [None, None, None],
        [1100, None, None]
    ]
}

spacing_against_components['small_locker'] = {
    'against_small_locker': [
        [1200, 900],
        [None, 0],
        [None, 0, 0]
    ],
    'against_low_cabinet': [
        [1200, 900, None],
        [900, 0, 0],
        [None, 0, 0]
    ],
    'against_storage': [
        [1200, None, None],
        [1100, 0, None],
        [None, None, None]
    ],
    'against_printer_set': [
        [1200, 900, None],
        [1100, 100, 100],
        [1100, 100, 100]
    ]
}

spacing_against_components['low_cabinet'] = {
    'against_low_cabinet': [
        [1200, 900],
        [None, 0],
        [None, 0, 0]
    ],
    'against_storage': [
        [1200, 900, None],      # to support non-existing combinations of placements in temporary
        [900, None, None],
        [None, None, None]
    ],
    'against_printer_set': [
        [1200, 900, None],
        [1100, 100, 100],
        [1100, 100, 100]
    ]
}

spacing_against_components['storage'] = {
    'against_storage': [
        [1200, 900, None],
        [900, 900, None],
        [None, None, 0]
    ],
    'against_printer_set': [
        [1200, 900, None],
        [1100, 100, 100],
        [1100, 100, None]
    ]
}

spacing_against_components['printer_set'] = {
    'against_printer_set': [
        [1200, 900],
        [900, 100],
        [None, None, None]
    ]
}


# below against all kinds of boundaries:
#   - note: in order of (longside(with open door), shortside, longside(with closed door))
spacing_against_boundaries = {}
spacing_against_boundaries['desk'] = {
    'against_wall': [1200, 800, 0],
    'against_window': [1200, 800, 0],
    'against_main_passageway': [0, 0, 0]
}

spacing_against_boundaries['accompany_seat'] = {
    'against_wall': [900, 800],
    'against_window': [900, 800],
    'against_main_passageway': [None, None]
}

spacing_against_boundaries['storage'] = {
    'against_wall': [1100, 0, 0],
    'against_window': [None, None, 400],
    'against_main_passageway': [0, 0, 0],
    'against_door': [300, 300, None]
}

spacing_against_boundaries['printer_set'] = {
    'against_wall': [0, 100, 100],
    'against_window': [100, None, 100],
    'against_main_passageway': [0, 0, 0],
    'against_door': [300, 300, None]
}

spacing_against_boundaries['low_cabinet'] = {
    'against_wall': [900, 0, 0],
    'against_window': [900, 400, 0],
    'against_main_passageway': [0, 0, 0]
}

spacing_against_boundaries['small_locker'] = {
    'against_wall': [900, 0, 0],
    'against_window': [900, 400, 0],
    'against_main_passageway': [0, 0, 0]
}

main_passageway_width = 1600
additional_passageway_width = 300 
# s.t., there would existing 900 + 300 = 1200 passageway to office rooms
additional_spacing2door = main_passageway_width - 300

# spacing = {**spacing_against_components, **spacing_against_boundaries}
spacing = {}
keys = set(list(spacing_against_components.keys()) + list(spacing_against_boundaries.keys()))
for key in keys:
    values = {}
    if key in spacing_against_components.keys():
        values = {**values, **spacing_against_components[key]}
    if key in spacing_against_boundaries.keys():
        values = {**values, **spacing_against_boundaries[key]}
    spacing[key] = values


__map_side_to_index = lambda side: 0 if side == 'longside' else 1

wall_width = 70