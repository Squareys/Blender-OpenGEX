from enum import IntEnum

from collections import OrderedDict

__author__ = 'Eric Lengyel, Jonathan Hale, Nicolas Wehrle'


class NodeType(IntEnum):
    node = 0
    bone = 1
    geometry = 2
    light = 3
    camera = 4


class ExporterState:
    def __init__(self, export_all, sample_animation, scene):
        self.nodes = []
        self.exportAll = export_all
        self.sampleAnimation = sample_animation
        self.boneParentArray = {}

        self.beginFrame = scene.frame_start
        self.endFrame = scene.frame_end
        self.frameTime = 1.0 / (scene.render.fps_base * scene.render.fps)

        self.geometryArray = {}
        self.lightArray = OrderedDict()
        self.cameraArray = {}
        self.materialArray = {}

    def find_node_wrapper_by_name(self, node_name):
        for nw in self.nodes:
            if nw.item.name == node_name:
                return nw

        return None
