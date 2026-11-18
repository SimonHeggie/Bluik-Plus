# SPDX-License-Identifier: GPL-3.0-or-later
"""Bluik rotation/scale extensions; these are not official OCA 1.3 fields.

v0.8.2 convention: degrees, scalar about Blender Y; three values are direct
Blender XYZ Euler additions to the image-plane X=90 degree basis.
"""
import math


def number(value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):
        raise ValueError('OCA transform values must be finite numbers')
    return float(value)


def rotation(value):
    if value is None:return (0.,0.,0.)
    if isinstance(value,(int,float)) and not isinstance(value,bool):return (0.,math.radians(number(value)),0.)
    if isinstance(value,(list,tuple)):
        if len(value)==1:return rotation(value[0])
        if len(value)==3:return tuple(math.radians(number(v)) for v in value)
    raise ValueError('OCA rotation must be degrees as one value or three XYZ values')


def scale(value,vector=False):
    if value is None:return (1.,1.,1.)
    if isinstance(value,(int,float)) and not isinstance(value,bool):value=(value,value)
    if isinstance(value,(list,tuple)) and len(value) in (2,3):
        values=tuple(number(v) for v in value)
        if len(values)==3:return values
        return (values[0],1.,values[1]) if vector else (values[0],values[1],1.)
    raise ValueError('OCA scale must be one value, two image axes or three XYZ values')


def payload(layer,frame,key):
    value=frame.get(key) if frame else None
    return layer.get(key) if value is None else value


def apply(obj,layer,frame=None,vector=False):
    frame=frame or {}
    angles=rotation(payload(layer,frame,'rotation'))
    obj.rotation_mode='XYZ'
    obj.rotation_euler=(angles[0]+(0 if vector else math.pi/2),angles[1],angles[2])
    factors=scale(payload(layer,frame,'scale'),vector=vector)
    obj.scale=tuple(a*b for a,b in zip(obj.scale,factors))
    return factors
