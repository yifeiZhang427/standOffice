from .latest_spacing import spacing as latest_spacing, __map_side_to_index

sizes = {
    'desk': (1400, 700),
    'storage': (900, 450),
    'chair': (700, 700),
    'printer': (2221, 626),
    'paper_shredder': (500, 500)
}
sizes['printer_set'] = (sizes['printer'][0] + sizes['paper_shredder'][0] + latest_spacing['printer_set']['against_printer_set'][__map_side_to_index('shortside')][__map_side_to_index('shortside')], 
                        max(sizes['printer'][1], sizes['paper_shredder'][1]))

main_passageway_width = 1600
storage_spacing = 1200
spacing = {
    'desk': {
        'against_wall': {
            'longside': 1200,
            'shortside': 900
        },
        'against_self': {
            'longside': 1500,
            'shortside': 900,
        },
        'against_storage': {
            'longside': 1500,
            'shortside': 1100
        },
        'against_main_passageway': {
            'shortside': main_passageway_width
        },
        'against_printer_set': {
            'shortside': 1100,
            'longside': 1500
        }
    },
    'locker': {
        'against_self': {'longside': storage_spacing}
    },
    'cabinet': {
        'against_self': {'longside': storage_spacing},
        'against_window': {
            'longside': 400,
            'shortside': 800
        }    
    }
}

spacing['desk']['against_desk'] = spacing['desk']['against_self']
spacing['desk']['against_window'] = spacing['desk']['against_wall']
spacing['desk']['against_main_passageway']['longside'] = main_passageway_width + sizes['chair'][1]
spacing['desk']['against_office_wall'] = spacing['desk']['against_wall']
spacing['desk']['against_islands'] = {'longside': 0}

spacing['storage'] = {
    'against_wall': {
        'longside': 800,
        'shortside': 1100
    },
    'against_desk': spacing['desk']['against_storage'],
    'against_window': spacing['cabinet']['against_window'],
    'against_storage': {
        'longside': 1200,
        'shortside': 900
    },
    'against_main_passageway': {
        'longside': main_passageway_width,
        'shortside': main_passageway_width
    },
    'against_printer_set': {
        'longside': 1100,
        'shortside': 1100
    }
}
spacing['storage']['against_office_wall'] = spacing['storage']['against_wall']
spacing['storage']['against_islands'] = {'longside': 0}

spacing['accompaniment_seat'] = {
    'against_accompaniment_seat': {'shortside': 800},
    'against_desk': {'longside': 900},
    'against_window': {'longside': 900},
    'against_wall': {'longside': 900}
}

spacing['printer_set'] = {
    'against_printer_set': {
        'longside': 1100,
        'shortside': 200
    },
    'against_wall': {
        'longside': 1100,
        'shortside': 200
    }
}

storage = {
    'locker': {
       'small': 4,
        'big': 8 
    },
    'cabinet': {
        'low': 2.7,
        'high': 5.4
    }
}

passageway_width = 1600

window_size = 5 * sizes['storage'][0]

magnification = {
    'locker': 1,
    'cabinet': 1.5
}

rotations_of_directions = {
    'down': 0,
    'up': 180,
    'right': 90,
    'left': 270
}

spacing_in_4D = {
    'printer_set': {
        'against_storage': [
            [1100, 1100],
            [1100, 200]
        ],
        'against_printer_set': [
            [1100, 1100],
            [1100, 200]
        ]
    },
    'storage': {
        'against_printer_set': [
            [1100, 1100],
            [1100, 200]
        ],
        'against_wall': [
            [1200, 1100],
            [1100, 0]
        ],
        'against_storage' : [
            [1200, 1100],
            [1100, 0]
        ]
    },
    'desk': {
        'against_printer_set': [
            [1500, 1100],
            [1200, 1100]
        ],
        'against_storage': [
            [1500, 1100],
            [1100, 1100]
        ],
        'against_main_passageway': [
            [None, None],
            [1600, None]
        ]
    }
}