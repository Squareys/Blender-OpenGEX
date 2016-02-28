import unittest

__author__ = "Jonathan Hale"

# find all unittests in tests/
suite = unittest.TestLoader().discover('.', pattern='*Test.py', top_level_dir='.')

# run the found tests and exit with failure when not successful
if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
    exit(1)
