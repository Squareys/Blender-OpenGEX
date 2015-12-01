# =============================================================
#
#  Open Game Engine Exchange
#  http://opengex.org/
#
#  Export plugin for Blender
#  by Eric Lengyel
#
#  Version 1.2.0.0
#
#  Copyright 2015, Terathon Software LLC
#  Copyright 2015, Jonathan Hale
#  Copyright 2015, Nicolas Wehrle
#
#  This software is licensed under the Creative Commons
#  Attribution-ShareAlike 3.0 Unported License:
#
#  http://creativecommons.org/licenses/by-sa/3.0/deed.en_US
#
# =============================================================

import bpy

from io_scene_ogex.OpenGexExporter import OpenGexExporter

__author__ = 'Eric Lengyel, Jonathan Hale, Nicolas Wehrle'

bl_info = {
    "name": "OpenGEX format (.ogex)",
    "description": "OpenGEX Exporter",
    "author": "Eric Lengyel, Jonathan Hale, Nicolas Wehrle",
    "version": (1, 2, 0, 0),
    "location": "File > Import-Export",
    "category": "Import-Export"}


def menu_func(self, _):
    self.layout.operator(OpenGexExporter.bl_idname, text="OpenGEX (.ogex)")


def register():
    bpy.utils.register_class(OpenGexExporter)
    bpy.types.INFO_MT_file_export.append(menu_func)


def unregister():
    bpy.types.INFO_MT_file_export.remove(menu_func)
    bpy.utils.unregister_class(OpenGexExporter)


if __name__ == "__main__":
    register()
