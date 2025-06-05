#!/usr/bin/env python3
"""Test runner for the woodway-searchbot."""

import unittest
import asyncio
import sys


class AsyncioTestRunner(unittest.TextTestRunner):
    """Test runner that handles async tests properly."""

    def run(self, test):
        """Run the given test case or test suite."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return super().run(test)
        finally:
            loop.close()


class AsyncioTestCase(unittest.IsolatedAsyncioTestCase):
    """Base class for async test cases."""

    pass


if __name__ == "__main__":
    # Discover and run all tests
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover("bot/tests")

    # Run tests with asyncio support
    runner = AsyncioTestRunner(verbosity=2)
    result = runner.run(test_suite)

    # Return proper exit code
    sys.exit(not result.wasSuccessful())
