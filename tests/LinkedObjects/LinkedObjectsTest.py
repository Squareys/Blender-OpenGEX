import bpy
import os
import unittest

from tests import TestUtils

__author__ = 'Jonathan Hale'


class LinkedObjectsTest(TestUtils.OgexExporterTest):

    # name of the output file
    base_dir = os.path.dirname(os.path.realpath(__file__))
    filename = base_dir + os.sep + "Test.ogex"

    def testLinkedObjects(self):
        bpy.ops.wm.open_mainfile(filepath=self.base_dir + os.sep + "Test.blend")
        bpy.ops.export_scene.ogex(filepath=self.filename, rounding=3)

        self.assertFilesEqual(self.filename, self.base_dir + os.sep + "Expected.ogex")

if __name__ == '__main__':
    unittest.main()
