from org.ogex.blender.ExporterState import *
from org.ogex.blender.BaseWrapper import BaseWrapper

__author__ = 'Eric Lengyel, Jonathan Hale, Nicolas Wehrle'


class BoneWrapper(BaseWrapper):

    def __init__(self, bone, container, parent=None, offset=None):
        super().__init__(bone, container, parent, offset)

        self.process_bone()

        if len(bone.children) != 0:
            self.create_children(bone.children)

        if bone.dupli_group:
            offset = bone.dupli_group.dupli_offset
            self.create_children(bone.dupli_group.objects, offset)

    def process_bone(self, bone):
        if self.container.exportAllFlag or bone.select:
            self.nodeRef["nodeType"] = kNodeTypeBone
            self.nodeRef["structName"] = bytes("node" + str(len(self.container.nodes)), "UTF-8")

    def create_children(self, children, offset=None):
        for bone in children:
            self.children.append(BoneWrapper(bone, self.container, self, offset))
