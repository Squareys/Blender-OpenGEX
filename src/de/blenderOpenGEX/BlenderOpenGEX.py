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
    "name": "OpenGEX format (.ogex)",
    "description": "Terathon Software OpenGEX Exporter",
    "author": "Eric Lengyel",
    "version": (1, 1, 2, 3),
    "location": "File > Import-Export",
    "wiki_url": "http://opengex.org/",
    "category": "Import-Export"}


import bpy
from blenderOpenGEX.MyOpenGexExporter import OpenGexExporter


kNodeTypeNode = 0
kNodeTypeBone = 1
kNodeTypeGeometry = 2
kNodeTypeLight = 3
kNodeTypeCamera = 4

kAnimationSampled = 0
kAnimationLinear = 1
kAnimationBezier = 2

kExportEpsilon = 1.0e-6


structIdentifier = [B"Node $", B"BoneNode $", B"GeometryNode $", B"LightNode $", B"CameraNode $"]


subtranslationName = [B"xpos", B"ypos", B"zpos"]
subrotationName = [B"xrot", B"yrot", B"zrot"]
subscaleName = [B"xscl", B"yscl", B"zscl"]
deltaSubtranslationName = [B"dxpos", B"dypos", B"dzpos"]
deltaSubrotationName = [B"dxrot", B"dyrot", B"dzrot"]
deltaSubscaleName = [B"dxscl", B"dyscl", B"dzscl"]
axisName = [B"x", B"y", B"z"]


def menu_func(self, context):
    self.layout.operator(OpenGexExporter.bl_idname, text = "OpenGEX (.ogex)")

def register():
    bpy.utils.register_class(OpenGexExporter)
    bpy.types.INFO_MT_file_export.append(menu_func)

def unregister():
    bpy.types.INFO_MT_file_export.remove(menu_func)
    bpy.utils.unregister_class(OpenGexExporter)

if __name__ == "__main__":
    register()