import unittest
import os
import filecmp
from bpy import context

import blenderOpenGEX
from blenderOpenGEX.MyOpenGexExporter import *


class LinkedObjectsTest(unittest.TestCase):

    # name of the output file
    base_dir = os.path.dirname(os.path.realpath(__file__))
    filename = base_dir + "\\Test.ogex"

    def setUp(self):
        blenderOpenGEX.register()

    def tearDown(self):
        if os.path.isfile(self.filename):
            os.remove(self.filename)

    def testLinkedObjects(self):
        bpy.ops.wm.open_mainfile(filepath=self.base_dir + "\\Test.blend")
        bpy.ops.export_scene.ogex(filepath=self.filename)

        self.assertEqual(open(self.base_dir + "\\Test.ogex").read(), open(self.base_dir + "\\Expected.ogex").read())

if __name__ == '__main__':
    unittest.main()
