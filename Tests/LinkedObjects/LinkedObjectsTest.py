import unittest
import os
import filecmp
from bpy import context

import blenderOpenGEX
from blenderOpenGEX.MyOpenGexExporter import *


class LinkedObjectsTest(unittest.TestCase):

    def setUp(self):
        blenderOpenGEX.register()
        self.base_dir = os.path.dirname(os.path.realpath(__file__))

    def testLinkedObjects(self):
        bpy.ops.wm.open_mainfile(filepath=self.base_dir + "\\Test.blend")
        bpy.ops.export_scene.ogex(filepath=self.base_dir + "\\Test.ogex")

        self.assertEqual(open(self.base_dir + "\\Test.ogex").read(), open(self.base_dir + "\\Expected.ogex").read())

if __name__ == '__main__':
    unittest.main()
