# <pep8 compliant>

import bpy # pylint: disable=import-error
from re import findall

def get_bpy_struct( obj_id, path):
    """ Gets a bpy_struct or property from an ID and an RNA path
        Returns None in case the path is invalid
        """
    try:
        # this regexp matches with two results: first word and what's in brackets if any
        # "prop['test']" -> [("prop", "'test'")]
        # "prop" -> [("prop","")]
        # "prop[12]" -> [("prop","12")]
        matches = findall( r'(\w+)?(?:\[([^\]]+)\])?' , path )
        for i,match in enumerate(matches) :
            attr = match[0]
            arr = match[1]
            if i == len(matches) -2:
                if attr != '' and  arr != '':
                    obj_id = getattr(obj_id, attr)
                    return obj_id, '[' + arr + ']'
                elif attr != '':
                    return obj_id, attr
                else:
                    return obj_id, '[' + arr + ']'
            if attr != '':
                obj_id = getattr(obj_id, attr)
            if arr != '':
                obj_id = obj_id[ eval(arr) ]
        return None           
    except:
        return None
