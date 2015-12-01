from blenderOpenGEX.BoneWrapper import BoneWrapper

__author__ = 'aullik'

from blenderOpenGEX.FlagContainer import *
from blenderOpenGEX.BaseWrapper import BaseWrapper


class NodeWrapper(BaseWrapper):

    def __init__(self, node, container, parent=None, offset=None):
        super().__init__(node, container, parent, offset)

        self.bones = []

        self.process_node()

        if len(node.children) != 0:
            self.create_children(node.children)

        if node.dupli_type == 'GROUP' and node.dupli_group:
            offset = node.dupli_group.dupli_offset
            self.create_children(node.dupli_group.objects, offset)

    def create_children(self, children, offset=None):
        for obj in children:
            self.children.append(NodeWrapper(obj, self.container, self, offset))

    def process_node(self):
        if self.container.exportAllFlag or self.item.select:
            self.nodeRef["nodeType"] = self.get_node_type()
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
                            self.bones.append(BoneWrapper(bone, self.container))

    def get_node_type(self):
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
