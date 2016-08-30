# =============================================================
#
#  Open Game Engine Exchange
#  http://opengex.org/
#
#  Inofficial Export plugin for Blender by Jonathan Hale,
#  based on the official Export plugin by Eric Lengyel
#
#  Version 1.1.2.1
#
# Copyright © 2015, 2016 Jonathan Hale
# Copyright © 2015 Terathon Software LLC
# Copyright © 2015 Nicolas Wehrle
#
# This software is licensed under the Creative Commons
# Attribution-ShareAlike 3.0 Unported License:
#
# http://creativecommons.org/licenses/by-sa/3.0/deed.en_US
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
# PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
# FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
# =============================================================

import bpy

from io_scene_ogex.OpenGexExporter import OpenGexExporter

__author__ = ' Jonathan Hale, Eric Lengyel,Nicolas Wehrle'

bl_info = {
    "name": "OpenGEX format (.ogex)",
    "description": "OpenGEX Exporter",
    "author": "Jonathan Hale, Eric Lengyel, Nicolas Wehrle",
    "version": (1, 1, 2, 1),
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
