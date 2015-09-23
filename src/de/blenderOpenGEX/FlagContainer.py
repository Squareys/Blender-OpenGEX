from blenderOpenGEX import debug

__author__ = 'aullik'

kNodeTypeNode = 0
kNodeTypeBone = 1
kNodeTypeGeometry = 2
kNodeTypeLight = 3
kNodeTypeCamera = 4


class FlagContainer:
    def __init__(self, exportAllFlag, sampleAnimationFlag, scene):
        debug()
        self.nodes = []
        self.exportAllFlag = exportAllFlag
        self.sampleAnimationFlag = sampleAnimationFlag
        self.boneParentArray = {}

        self.beginFrame = scene.frame_start
        self.endFrame = scene.frame_end
        self.frameTime = 1.0 / (scene.render.fps_base * scene.render.fps)

        self.geometryArray = {}
        self.lightArray = {}
        self.cameraArray = {}
        self.materialArray = {}

    def findNodeWrapperByName(self, nodeName):
        debug()
        for nw in self.nodes:
            if nw.item.name == nodeName:
                return nw

        return None
