

def __combine_multiple_defaultdictlists(*defaultdictlists):
    keys = set(key for _dict in defaultdictlists for key in _dict.keys())

    resulting_defaultdict = {}
    for key in keys:
        values = []
        for _dict in defaultdictlists:
            if key in _dict.keys():
                values += _dict[key]
        resulting_defaultdict[key] = values
    return resulting_defaultdict