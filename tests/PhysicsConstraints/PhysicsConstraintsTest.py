import bpy
import os
import unittest

from tests import TestUtils

__author__ = 'Jonathan Hale'


class PhysicsConstraintsTest(TestUtils.OgexExporterTest):

    # name of the output file
    base_dir = os.path.dirname(os.path.realpath(__file__))

    def testPhysicsConstraints(self):
        self.no_delete = True
        self.filename = self.base_dir + os.sep + "Test.ogex"
        bpy.ops.wm.open_mainfile(filepath=self.base_dir + os.sep + "Test.blend")
        bpy.ops.export_scene.ogex(filepath=self.filename, export_physics=True, rounding=3)

        self.assertFilesEqual(self.filename, self.base_dir + os.sep + "Expected.ogex")

if __name__ == '__main__':
    unittest.main()
