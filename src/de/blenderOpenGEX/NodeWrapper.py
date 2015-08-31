__author__ = 'aullik'

from blenderOpenGEX import debug

NodeCounter = 0

kNodeTypeNode = 0
kNodeTypeBone = 1
kNodeTypeGeometry = 2
kNodeTypeLight = 3
kNodeTypeCamera = 4

_allNodes = {}


def processSkinnedMesh():
    debug()
    for nw in _allNodes.values():
        if nw.nodeRef["nodeType"] == kNodeTypeGeometry:
            armature = nw.node.find_armature()
            if armature:
                for bone in armature.data.bones:
                    boneRef = findNodeWrapperByName(bone.name)
                    if boneRef:
                        # If a node is used as a bone, then we force its type to be a bone.
                        boneRef.dict["nodeType"] = kNodeTypeBone


def findNodeWrapper(node):
    if node in _allNodes:
        return _allNodes[node]

    return None


def findNodeWrapperByName(nodeName):
    for key in _allNodes:
        if key.ame == nodeName:
            return _allNodes[key]

    return None


class NodeWrapper:

    def __init__(self, node, parent=None, offset=None):
        _allNodes[node] = self

        self.node = node
        self.parent = parent
        self.children = []
        self.offset = offset
        self.nodeRef = {}

        self.processNode()

        if len(node.children) != 0:
            self.createChildren(node.children)

        if node.dupli_group:
            offset = node.dupli_group.dupli_offset
            self.createChildren(node.dupli_group.objects, offset)

    def createChildren(self, children, offset=None):
        for obj in children:
            self.children.append(NodeWrapper(obj, self, offset))

    def processNode(self):
        debug()
        if self.exportAllFlag or self.node.select:
            global NodeCounter
            NodeCounter += 1
            self.nodeRef["nodeType"] = self.getNodeType()
            self.nodeRef["structName"] = bytes("node" + str(NodeCounter), "UTF-8")

            if self.node.parent_type == "BONE":
                boneSubnodeArray = self.boneParentArray.get(self.node.parent_bone)
                if boneSubnodeArray:
                    boneSubnodeArray.append(self.node)
                else:
                    self.boneParentArray[self.node.parent_bone] = [self.node]

            if self.node.type == "ARMATURE":
                skeleton = self.node.data
                if skeleton:
                    for bone in skeleton.bones:
                        if not bone.parent:
                            self.ProcessBone(bone)

    def getNodeType(self):
        debug()
        if self.node.type == "MESH":
            if len(self.node.data.polygons) != 0:
                return kNodeTypeGeometry
        elif self.node.type == "LAMP":
            type = self.node.data.type
            if (type == "SUN") or (type == "POINT") or (type == "SPOT"):
                return kNodeTypeLight
        elif self.node.type == "CAMERA":
            return kNodeTypeCamera

        return kNodeTypeNode
