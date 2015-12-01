import unittest
import os
from bpy import context

import blenderOpenGEX
from blenderOpenGEX.MyOpenGexExporter import *


class LinkedObjectsTest(unittest.TestCase):
    def test_something(self):
        blenderOpenGEX.register()

        base_dir = os.path.dirname(os.path.realpath(__file__))

        bpy.ops.wm.open_mainfile(filepath=base_dir + "\\Test.blend")

        bpy.ops.export_scene.ogex(filepath=base_dir + "\\Test.ogex")
        self.assertEqual(True, False)

if __name__ == '__main__':
    unittest.main()
