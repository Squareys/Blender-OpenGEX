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


def printCaller():
    # FIXME REMOVE
    f = sys._getframe(2)

    method = f.f_code.co_name

    if 'self' in f.f_locals:
        classname = f.f_locals['self'].__class__.__name__

    else:
        call = traceback.extract_stack(f)[-2][3]
        classname = call.replace('.' + method + '()', '')

    return classname + ' - ' + method + ' : '



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
