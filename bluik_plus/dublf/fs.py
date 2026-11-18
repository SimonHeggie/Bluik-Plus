# <pep8 compliant>

import os
import bpy # pylint: disable=import-error

# File system tools

def get_fileBaseName( file ):
    """Gets the name part of a file without the extension"""
    filename = ""
    if isinstance(file, bpy.types.OperatorFileListElement):
        filename = file.name
    else:
        try:
            filename = file.stem
        except:
            pass
    return os.path.basename(filename)
