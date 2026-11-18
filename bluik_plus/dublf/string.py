"""String utils"""

def intToStr( i, numDigits=3 ):
    """Converts an int to a string, with leading zeros"""
    i_str = str(i)
    while len(i_str) < numDigits:
        i_str = '0' + i_str
    return i_str
