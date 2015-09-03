from blenderOpenGEX.BoneWrapper import BoneWrapper

__author__ = 'aullik'

from blenderOpenGEX.FlagContainer import *
from blenderOpenGEX.BaseWrapper import BaseWrapper
from blenderOpenGEX import debug


class NodeWrapper(BaseWrapper):

    def __init__(self, node, container, parent=None, offset=None):
        debug()
        super().__init__(node, container, parent, offset)

        self.bones = []

        self.processNode()

        if len(node.children) != 0:
            self.createChildren(node.children)

        if node.dupli_group:
            offset = node.dupli_group.dupli_offset
            self.createChildren(node.dupli_group.objects, offset)

    def createChildren(self, children, offset=None):
        debug()
        for obj in children:
            self.children.append(NodeWrapper(obj, self.container, self, offset))

    def processNode(self):
        debug()
        if self.container.exportAllFlag or self.item.select:
            self.nodeRef["nodeType"] = self.getNodeType()
            self.nodeRef["structName"] = bytes("node" + str(len(self.container.nodes)), "UTF-8")

            if self.item.parent_type == "BONE":
                boneSubnodeArray = self.container.boneParentArray.get(self.item.parent_bone)
                if boneSubnodeArray:
                    boneSubnodeArray.append(self)
                else:
                    self.container.boneParentArray[self.item.parent_bone] = [self]

            if self.item.type == "ARMATURE":
                skeleton = self.item.data
                if skeleton:
                    for bone in skeleton.bones:
                        if not bone.parent:
                            # FIXME register somehow
                            self.boney.append(BoneWrapper(bone, self.container))

    def getNodeType(self):
        debug()
        if self.item.type == "MESH":
            if len(self.item.data.polygons) != 0:
                return kNodeTypeGeometry
        elif self.item.type == "LAMP":
            type = self.item.data.type
            if (type == "SUN") or (type == "POINT") or (type == "SPOT"):
                return kNodeTypeLight
        elif self.item.type == "CAMERA":
            return kNodeTypeCamera

        return kNodeTypeNode
