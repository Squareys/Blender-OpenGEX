from io_scene_ogex.BaseWrapper import BaseWrapper
from io_scene_ogex.ExporterState import *

from io_scene_ogex.BoneWrapper import BoneWrapper

__author__ = 'Eric Lengyel, Jonathan Hale, Nicolas Wehrle'


class NodeWrapper(BaseWrapper):

    def __init__(self, node, container, parent=None, offset=None):
        super().__init__(node, container, parent, offset)

        self.bones = []

        self.process_node()

        if len(node.children) != 0:
            self.create_children(node.children)

        if node.dupli_type == 'GROUP' and node.dupli_group:
            offset = node.dupli_group.dupli_offset
            self.create_children([o for o in node.dupli_group.objects if o.parent is None], offset)

    def create_children(self, children, offset=None):
        for obj in children:
            self.children.append(NodeWrapper(obj, self.container, self, offset))

    def process_node(self):
        if self.container.exportAll or self.item.select:
            self.nodeRef["nodeType"] = self.get_node_type()
            self.nodeRef["structName"] = bytes("node" + str(len(self.container.nodes)), "UTF-8")

            if self.item.parent_type == "BONE":
                bone_subnode_array = self.container.boneParentArray.get(self.item.parent_bone)
                if bone_subnode_array:
                    bone_subnode_array.append(self)
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
            if len(self.item.data.vertices) != 0:
                return NodeType.geometry
        elif self.item.type == "LAMP":
            lamp_type = self.item.data.type
            if (lamp_type == "SUN") or (lamp_type == "POINT") or (lamp_type == "SPOT"):
                return NodeType.light
        elif self.item.type == "CAMERA":
            return NodeType.camera

        return NodeType.node
