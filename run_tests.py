import unittest
suite = unittest.TestLoader().discover('.', pattern='*Test.py', top_level_dir='.')
if not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful():
    exit(1)
