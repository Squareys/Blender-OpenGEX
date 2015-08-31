__author__ = 'aullik'

# =============================================================
#
#  Open Game Engine Exchange
#  http://opengex.org/
#
#  Export plugin for Blender
#  by Eric Lengyel
#
#  Version 1.1.2.3
#
#  Copyright 2015, Terathon Software LLC
#
#  This software is licensed under the Creative Commons
#  Attribution-ShareAlike 3.0 Unported License:
#
#  http://creativecommons.org/licenses/by-sa/3.0/deed.en_US
#
# =============================================================

bl_info = {
    "name": "NEW OpenGEX format (.ogex)",
    "description": "OpenGEX Exporter",
    "author": "aullik",
    "version": (1, 1, 2, 3),
    "location": "File > Import-Export",
    "category": "Import-Export"}

import sys
import traceback


def debug():
    _printCaller()


def _printCaller():
    self = sys._getframe(2)
    if self.f_back is None:
        parent = 'None - None'
    else:
        parent = _getClassAndMethod(self.f_back)

    args = ''
    first = True

    for k, v in self.f_locals.items():
        if k == 'self':
            continue

        if first:
            first = False
        else:
            args += ', '

        args += k + ': ' + str(v)

    out = parent + ' : ' + _getClassAndMethod(self) + ' :-: ' + args
    print(out)


def _getClassAndMethod(frame):
    method = frame.f_code.co_name

    if 'self' in frame.f_locals:
        classname = frame.f_locals['self'].__class__.__name__

    else:
        stack = traceback.extract_stack(frame)
        if(len(stack)< 2):
            classname =stack[0][0].rsplit('/', 1)[1]
            method = 'None'
        else:
            call = stack[-2][3]
            classname = call.replace('.' + method + '()', '')

    return classname + ' - ' + method


import bpy
from blenderOpenGEX.MyOpenGexExporter import OpenGexExporter


def menu_func(self, context):
    # FIXME REMOVE
    print('__init__ - menu_func -', self, context)
    self.layout.operator(OpenGexExporter.bl_idname, text="OpenGEX (.ogex)")


def register():
    # FIXME REMOVE
    print('__init__ - register -')
    bpy.utils.register_class(OpenGexExporter)
    bpy.types.INFO_MT_file_export.append(menu_func)


def unregister():
    # FIXME REMOVE
    print('__init__ - unregister -')
    bpy.types.INFO_MT_file_export.remove(menu_func)
    bpy.utils.unregister_class(OpenGexExporter)


if __name__ == "__main__":
    register()
