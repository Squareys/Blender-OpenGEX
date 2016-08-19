import bpy
import os
import unittest

from tests import TestUtils

__author__ = 'Jonathan Hale'


# Regression test for exporting image textures
class ImageTextureTest(TestUtils.OgexExporterTest):

    # name of the output file
    base_dir = os.path.dirname(os.path.realpath(__file__))
    filename = base_dir + os.sep + "Test.ogex"

    def testImageTextureExport(self):
        bpy.ops.wm.open_mainfile(filepath=self.base_dir + os.sep + "Test.blend")
        bpy.ops.export_scene.ogex(filepath=self.filename, rounding=3,
                                  export_image_textures=True, image_path_prefix="textures/",
                                  image_format='BMP')

        self.assertFilesEqual(self.filename, self.base_dir + os.sep + "Expected.ogex")
        self.assertTrue(os.path.isfile(os.path.join(self.base_dir, "textures", "Test.bmp")))

if __name__ == '__main__':
    unittest.main()
