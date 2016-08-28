import bpy
import os
import unittest

from tests import TestUtils

__author__ = 'Jonathan Hale'


class KeframeAnimationTest(TestUtils.OgexExporterTest):

    # name of the output file
    base_dir = os.path.dirname(os.path.realpath(__file__))

    def testKeyframeAnimation(self):
        bpy.ops.wm.open_mainfile(filepath=self.base_dir + os.sep + "TestSimple.blend")

        self.filename = self.base_dir + os.sep + "TestSimple.ogex"
        bpy.ops.export_scene.ogex(filepath=self.filename)
        self.assertFilesEqual(self.filename, self.base_dir + os.sep + "TestSimpleExpected.ogex")

    def testKeyframeAnimationSampled(self):
        bpy.ops.wm.open_mainfile(filepath=self.base_dir + os.sep + "TestSimple.blend")

        self.filename = self.base_dir + os.sep + "TestSimpleSampled.ogex"
        bpy.ops.export_scene.ogex(filepath=self.filename, sample_animation=True)
        self.assertFilesEqual(self.filename, self.base_dir + os.sep + "TestSimpleSampled.ogex")

if __name__ == '__main__':
    unittest.main()
