def is_int_item(item):
    # note: length test helps identify numpy arrays with one element which
    # can be casted to int but is inconsistent with what we expect from
    # array based indexing.
    haslen = False
    try:
        len(item)
        haslen = True
    except TypeError:
        pass

    isint = False
    try:
        int(item)
        isint = True
    except TypeError:
        pass

    return not haslen and isint
