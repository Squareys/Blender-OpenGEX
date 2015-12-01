__author__ = 'Eric Lengyel, Jonathan Hale, aullik'


class BaseWrapper:

    def __init__(self, item, container, parent, offset):
        self.parent = parent
        self.children = []
        self.item = item
        self.container = container
        self.offset = offset
        self.nodeRef = {}

        self.container.nodes.append(self)


