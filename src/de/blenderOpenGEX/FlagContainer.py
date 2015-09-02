__author__ = 'aullik'

kNodeTypeNode = 0
kNodeTypeBone = 1
kNodeTypeGeometry = 2
kNodeTypeLight = 3
kNodeTypeCamera = 4


class FlagContainer:
    def __init__(self, exportAllFlag, sampleAnimationFlag, scene, file):
        self.nodes = []
        self.exportAllFlag = exportAllFlag
        self.sampleAnimationFlag = sampleAnimationFlag
        self.boneParentArray = {}

        self.file = file
        self.indentLevel = 0

        self.beginFrame = scene.frame_start
        self.endFrame = scene.frame_end
        self.frameTime = 1.0 / (scene.render.fps_base * scene.render.fps)

        self.geometryArray = {}
        self.lightArray = {}
        self.cameraArray = {}
        self.materialArray = {}

    def findNodeWrapperByName(self, nodeName):
        for nw in self.nodes:
            if nw.item.name == nodeName:
                return nw

        return None
