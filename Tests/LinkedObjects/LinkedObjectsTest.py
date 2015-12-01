import os
import unittest

import org.ogex.blender
from org.ogex.blender.OpenGexExporter import *

__author__ = 'Jonathan Hale'


class LinkedObjectsTest(unittest.TestCase):

    # name of the output file
    base_dir = os.path.dirname(os.path.realpath(__file__))
    filename = base_dir + os.sep + "Test.ogex"

    def setUp(self):
        org.ogex.blender.register()

    def tearDown(self):
        if os.path.isfile(self.filename):
            os.remove(self.filename)

    def testLinkedObjects(self):
        bpy.ops.wm.open_mainfile(filepath=self.base_dir + os.sep + "Test.blend")
        bpy.ops.export_scene.ogex(filepath=self.filename)

        self.assertEqual(open(self.filename).read(), open(self.base_dir + os.sep + "Expected.ogex").read())

if __name__ == '__main__':
    unittest.main()
