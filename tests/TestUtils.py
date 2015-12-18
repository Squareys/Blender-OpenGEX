
import os
import unittest

import io_scene_ogex

__author__ = 'Jonathan Hale'


class OgexExporterTest(unittest.TestCase):

    def setUp(self):
        io_scene_ogex.register()

    def tearDown(self):
        if os.path.isfile(self.filename):
            os.remove(self.filename)
        io_scene_ogex.unregister()

    def readContents(self, filename):
        """
        Open, read the contents and then close a file.
        :param filename: name of the file to read the contents of
        :return: Contents of the file with given filename
        """
        file = open(filename)
        contents = file.read()
        file.close()

        return contents

    def assertFilesEqual(self, test_filename, expected_filename):
        """
        Check whether the contents of two files are equal
        :param test_filename: name of the file to test
        :param expected_filename: name of the file containing expected content
        """
        self.assertEqual(self.readContents(test_filename), self.readContents(expected_filename))
