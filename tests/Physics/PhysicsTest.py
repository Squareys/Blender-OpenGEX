import bpy
import os
import unittest

from tests import TestUtils

__author__ = 'Jonathan Hale'


class PhysicsTest(TestUtils.OgexExporterTest):

    # name of the output file
    base_dir = os.path.dirname(os.path.realpath(__file__))

    def testBasicProperties(self):
        self.filename = self.base_dir + os.sep + "BasicProperties.ogex"
        bpy.ops.wm.open_mainfile(filepath=self.base_dir + os.sep + "BasicProperties.blend")
        bpy.ops.export_scene.ogex(filepath=self.filename, export_physics=True, rounding=3)

        self.assertFilesEqual(self.filename, self.base_dir + os.sep + "BasicPropertiesExpected.ogex")

    def testAdvancedProperties(self):
        self.filename = self.base_dir + os.sep + "AdvancedProperties.ogex"
        bpy.ops.wm.open_mainfile(filepath=self.base_dir + os.sep + "AdvancedProperties.blend")
        bpy.ops.export_scene.ogex(filepath=self.filename, export_physics=True, rounding=3)

        self.assertFilesEqual(self.filename, self.base_dir + os.sep + "AdvancedPropertiesExpected.ogex")

if __name__ == '__main__':
    unittest.main()
