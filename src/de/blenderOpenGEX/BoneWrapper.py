from blenderOpenGEX.BaseWrapper import BaseWrapper
from blenderOpenGEX.FlagContainer import *
from blenderOpenGEX import debug


__author__ = 'aullik'


class BoneWrapper(BaseWrapper):

    def __init__(self, bone, container, parent=None, offset=None):
        debug()
        super().__init__(bone, container, parent, offset)

        self.processBone()

        if len(bone.children) != 0:
            self.createChildren(bone.children)

        if bone.dupli_group:
            offset = bone.dupli_group.dupli_offset
            self.createChildren(bone.dupli_group.objects, offset)

    def processBone(self, bone):
        debug()
        if self.container.exportAllFlag or bone.select:
            self.nodeRef["nodeType"] = kNodeTypeBone
            self.nodeRef["structName"] = bytes("node" + str(len(self.container.nodes)), "UTF-8")

    def createChildren(self, children, offset=None):
        debug()
        for bone in children:
            self.children.append(BoneWrapper(bone, self.container, self, offset))
