import bpy
import os
import unittest

import io_scene_ogex

__author__ = 'Jonathan Hale'


class CustomProperties(unittest.TestCase):

    # name of the output file
    base_dir = os.path.dirname(os.path.realpath(__file__))
    filename = base_dir + os.sep + "Test.ogex"

    def setUp(self):
        io_scene_ogex.register()

    def tearDown(self):
        if os.path.isfile(self.filename):
            os.remove(self.filename)

    def testCustomProperties(self):
        bpy.ops.wm.open_mainfile(filepath=self.base_dir + os.sep + "Test.blend")
        bpy.ops.export_scene.ogex(filepath=self.filename)

        self.assertEqual(open(self.filename).read(), open(self.base_dir + os.sep + "Expected.ogex").read())

if __name__ == '__main__':
    unittest.main()
