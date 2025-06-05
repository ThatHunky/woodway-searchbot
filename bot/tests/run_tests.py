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


class AsyncioTestCase(unittest.TestCase):
    """Base class for async test cases."""
    
    def __init__(self, methodName='runTest'):
        super().__init__(methodName)
        # Get the test method
        method = getattr(self, methodName)
        # If it's a coroutine, wrap it
        if asyncio.iscoroutinefunction(method):
            setattr(self, methodName, self._run_coroutine(method))
    
    def _run_coroutine(self, coroutine):
        """Wrap coroutine to run in the event loop."""
        def wrapper(*args, **kwargs):
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(coroutine(*args, **kwargs))
        return wrapper


if __name__ == "__main__":
    # Discover and run all tests
    test_loader = unittest.TestLoader()
    test_suite = test_loader.discover("bot/tests")
    
    # Run tests with asyncio support
    runner = AsyncioTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Return proper exit code
    sys.exit(not result.wasSuccessful()) 