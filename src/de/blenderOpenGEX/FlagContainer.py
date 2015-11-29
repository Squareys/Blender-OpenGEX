from blenderOpenGEX import debug

__author__ = ['aullik', 'Squareys']

kNodeTypeNode = 0
kNodeTypeBone = 1
kNodeTypeGeometry = 2
kNodeTypeLight = 3
kNodeTypeCamera = 4


class FlagContainer:
    def __init__(self, export_all, sample_animation, scene):
        debug()
        self.nodes = []
        self.exportAllFlag = export_all
        self.sampleAnimationFlag = sample_animation
        self.boneParentArray = {}

        self.beginFrame = scene.frame_start
        self.endFrame = scene.frame_end
        self.frameTime = 1.0 / (scene.render.fps_base * scene.render.fps)

        self.geometryArray = {}
        self.lightArray = {}
        self.cameraArray = {}
        self.materialArray = {}

    def find_node_wrapper_by_name(self, node_name):
        debug()
        for nw in self.nodes:
            if nw.item.name == node_name:
                return nw

        return None
