import argparse
import importlib
import os
import sys
import unittest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # ignore list
    parser.add_argument("--ignore", nargs="+", default=[])
    args = parser.parse_args()
    ignores = set(args.ignore)
    #
    cur_path = os.path.dirname(os.path.abspath(__file__))
    if cur_path not in sys.path:
        sys.path.append(cur_path)
    #
    modules = os.listdir(cur_path)
    unittest_classes = []
    for file in modules:
        if file.endswith(".py") and file != "__init__.py" and os.path.join(cur_path, file) != os.path.abspath(__file__):
            name = file[:-3]
            if name in ignores or (name.endswith("_test") and name[:-5] in ignores):
                print(f"Skipping {name}")
                continue
            module = importlib.import_module(file[:-3])
            for name, obj in module.__dict__.items():
                if isinstance(obj, type) and issubclass(obj, unittest.TestCase):
                    unittest_classes.append(obj)
    #
    suite = unittest.TestSuite()
    for test_class in unittest_classes:
        tests = unittest.defaultTestLoader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    runner = unittest.TextTestRunner()
    #
    sys.path.append(os.path.dirname(cur_path))
    runner.run(suite)