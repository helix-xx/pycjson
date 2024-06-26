import os
import sys
import unittest

import json
import math
import random
import time
import gc


class FuzzGenerator:
    """A random JSON serialisable object generator."""

    def __init__(self, seed=None):
        self._randomizer = random.Random(seed)
        self._shrink = 1

    def key(self):
        key_types = [self.int, self.float, self.string, self.null, self.bool]
        return self._randomizer.choice(key_types)()

    def item(self):
        if self._randomizer.random() > 0.8:
            return self.key()
        return self._randomizer.choice([self.list, self.dict])()

    def int(self):
        return int(self.float())

    def float(self):
        sign = self._randomizer.choice([-1, 1, 0])
        return sign * math.exp(self._randomizer.uniform(-40, 40))

    def string(self):
        characters = ["\x00", "\t", "a", "\U0001f680", "<></>", "\u1234"]
        return self._randomizer.choice(characters) * self.length()

    def bool(self):
        return self._randomizer.random() < 0.5

    def null(self):
        return None

    def list(self):
        return [self.item() for i in range(self.length())]

    def dict(self):
        return {self.key(): self.item() for i in range(self.length())}

    def length(self):
        self._shrink *= 0.99
        return int(math.exp(self._randomizer.uniform(-0.5, 5)) * self._shrink)
class TestMemory(unittest.TestCase):
    @staticmethod
    def collect_all_objects(obj):
        """Given an object, return a list of all objects referenced by it."""
        def _inner(o):
            yield o
            if isinstance(o, list):
                for v in o:
                    yield from _inner(v)
            elif isinstance(o, dict):
                for k, v in o.items():
                    yield from _inner(k)
                    yield from _inner(v)

        out = []
        seen = set()
        for o in _inner(obj):
            if id(o) not in seen and o is not None:
                seen.add(id(o))
                out.append(o)
        return out

    @staticmethod
    def random_object(seed=None):
        return FuzzGenerator(seed).item()

    def test_encode_leak(self):
        """
        Developed by ESN, an Electronic Arts Inc. studio.
        Copyright (c) 2014, Electronic Arts Inc.
        All rights reserved.

        Full licence text can be found in https://github.com/ultrajson/ultrajson.
        """
        # A brute force fuzzer for detecting memory issues in ujson.dumps(). To use, first
        # compile ujson in debug mode:

        #     CFLAGS='-DDEBUG' python setup.py -q build_ext --inplace -f

        # Then run without arguments:

        #     python tests/fuzz.py

        # If it crashes, the last line of output is the arguments to reproduce the
        # failure.

        #     python tests/fuzz.py {{ last line of output before crash }}

        # Adding --dump-python or --dump-json will print the object it intends to
        # serialise as either a Python literal or in JSON.
        if hasattr(sys, "pypy_version_info"):
            # PyPy's GC works differently (no ref counting), so this wouldn't be useful.
            # Simply returning an empty list effectively disables the refcount test.
            return []
        
        import cjson

        now = time.time()
        seeds = [now * i for i in range(1, 31)]
        for seed in seeds:
            data = self.random_object(seed)
            # print(f"--seed {seed}")

            data_objects = self.collect_all_objects(data)
            # Exclude ints because they get referenced by the lists below.
            data_objects = [o for o in data_objects if not isinstance(o, int)]
            gc.collect()
            data_ref_counts_before = [sys.getrefcount(o) for o in data_objects]
            cjson.dumps(data)
            gc.collect()
            data_ref_counts_after = [sys.getrefcount(o) for o in data_objects]
            if data_ref_counts_before != data_ref_counts_after:
                for o, before, after in zip(
                    data_objects, data_ref_counts_before, data_ref_counts_after
                ):
                    if before != after:
                        print(f"Ref count of {o!r} went from {before} to {after}")
                self.assertTrue(False, "Ref count changed")

    def test_decode_leak(self):
        if hasattr(sys, "pypy_version_info"):
            # skip PyPy
            return

        import gc
        import tracemalloc

        from test_utils import get_benchfiles_fullpath

        import cjson

        datas = []
        for file in get_benchfiles_fullpath():
            with open(file, "r", encoding='utf-8') as f:
                datas.append(f.read())

        # warm up. CPython will not release memory immediately.
        for data in datas:
            for _ in range(10):
                cjson.loads(data)
        #
        tracemalloc.start()
        #
        gc.collect()
        snapshot_1, peak_1 = tracemalloc.get_traced_memory()
        for data in datas:
            for _ in range(100):
                cjson.loads(data)
        gc.collect()
        snapshot_2, peak_2 = tracemalloc.get_traced_memory()
        #
        mem_diff = snapshot_2 - snapshot_1
        peak_diff = peak_2 - peak_1
        print(f"mem_diff: {mem_diff}, peak_diff: {peak_diff}")
        # should not increase more than 100 bytes
        self.assertGreaterEqual(100, mem_diff)
        
    def test_dump_leak_refcount(self):
        """
        Developed by ESN, an Electronic Arts Inc. studio.
        Copyright (c) 2014, Electronic Arts Inc.
        All rights reserved.

        Full licence text can be found in https://github.com/ultrajson/ultrajson.
        """
        # A brute force fuzzer for detecting memory issues in ujson.dumps(). To use, first
        # compile ujson in debug mode:

        #     CFLAGS='-DDEBUG' python setup.py -q build_ext --inplace -f

        # Then run without arguments:

        #     python tests/fuzz.py

        # If it crashes, the last line of output is the arguments to reproduce the
        # failure.

        #     python tests/fuzz.py {{ last line of output before crash }}

        # Adding --dump-python or --dump-json will print the object it intends to
        # serialise as either a Python literal or in JSON.
        if hasattr(sys, "pypy_version_info"):
            # PyPy's GC works differently (no ref counting), so this wouldn't be useful.
            # Simply returning an empty list effectively disables the refcount test.
            return []
        
        import cjson
        import tempfile

        now = time.time()
        seeds = [now * i for i in range(1, 31)]
        for seed in seeds:
            with tempfile.NamedTemporaryFile("w", delete=True) as f:
                data = self.random_object(seed)
                # print(f"--seed {seed}")

                data_objects = self.collect_all_objects(data)
                # Exclude ints because they get referenced by the lists below.
                data_objects = [o for o in data_objects if not isinstance(o, int)]
                gc.collect()
                data_ref_counts_before = [sys.getrefcount(o) for o in data_objects]
                cjson.dump(data, f)
                gc.collect()
                data_ref_counts_after = [sys.getrefcount(o) for o in data_objects]
                if data_ref_counts_before != data_ref_counts_after:
                    for o, before, after in zip(
                        data_objects, data_ref_counts_before, data_ref_counts_after
                    ):
                        if before != after:
                            print(f"Ref count of {o!r} went from {before} to {after}")
                    self.assertTrue(False, "Ref count changed")
                    
    def test_dump_leak(self):
        if hasattr(sys, "pypy_version_info"):
            # skip PyPy
            return

        import gc
        import tracemalloc

        from test_utils import get_benchfiles_fullpath

        import cjson
        import tempfile
        
        datas = []
        for file in get_benchfiles_fullpath():
            with open(file, "r", encoding='utf-8') as f:
                datas.append(json.load(f))

        # warm up. CPython will not release memory immediately.
        for data in datas:
            for _ in range(10):
                with tempfile.NamedTemporaryFile("w", delete=True) as f:
                    json.dump(data, f)
        #
        tracemalloc.start()
        #
        gc.collect()
        snapshot_1, peak_1 = tracemalloc.get_traced_memory()
        for data in datas:
            for _ in range(10):
                with tempfile.NamedTemporaryFile("w", delete=True) as f:
                    cjson.dump(data, f)
        gc.collect()
        snapshot_2, peak_2 = tracemalloc.get_traced_memory()
        #
        mem_diff = snapshot_2 - snapshot_1
        peak_diff = peak_2 - peak_1
        print(f"mem_diff: {mem_diff}, peak_diff: {peak_diff}")
        # should not increase more than 100 bytes
        self.assertGreaterEqual(100, mem_diff)
        
    def test_load_leak(self):
        if hasattr(sys, "pypy_version_info"):
            # skip PyPy
            return

        import gc
        import tracemalloc

        from test_utils import get_benchfiles_fullpath

        import cjson
        import json

        file_paths = get_benchfiles_fullpath()
        # warm up. CPython will not release memory immediately.
        for file in file_paths:
            for _ in range(10):
                with open(file, "r") as f:
                    cjson.load(f)
        #
        tracemalloc.start()
        #
        gc.collect()
        snapshot_1, peak_1 = tracemalloc.get_traced_memory()
        for file in file_paths:
            for _ in range(10):
                with open(file, "r") as f:
                    cjson.load(f)
        gc.collect()
        snapshot_2, peak_2 = tracemalloc.get_traced_memory()
        #
        mem_diff = snapshot_2 - snapshot_1
        peak_diff = peak_2 - peak_1
        print(f"mem_diff: {mem_diff}, peak_diff: {peak_diff}")
        # should not increase more than 100 bytes
        self.assertGreaterEqual(100, mem_diff)


if __name__ == "__main__":
    sys.path.append(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    unittest.main()
