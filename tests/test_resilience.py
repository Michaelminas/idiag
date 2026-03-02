"""Tests for error handling and resilience utilities."""

import pytest

from app.utils.resilience import with_fallback


class TestWithFallback:
    def test_normal_execution(self):
        @with_fallback(default="fallback_value")
        def good_func():
            return "success"

        assert good_func() == "success"

    def test_fallback_on_connection_error(self):
        @with_fallback(default="fallback_value")
        def bad_func():
            raise ConnectionError("offline")

        assert bad_func() == "fallback_value"

    def test_fallback_on_timeout(self):
        @with_fallback(default=None, log_message="API call failed")
        def bad_func():
            raise TimeoutError("timeout")

        assert bad_func() is None

    def test_fallback_on_os_error(self):
        @with_fallback(default={})
        def bad_func():
            raise OSError("disk full")

        assert bad_func() == {}

    def test_fallback_preserves_args(self):
        @with_fallback(default={})
        def func_with_args(a, b, key=None):
            raise OSError("nope")

        assert func_with_args(1, 2, key="test") == {}

    def test_no_fallback_for_type_error(self):
        @with_fallback(default="fallback")
        def buggy():
            raise TypeError("wrong type")

        with pytest.raises(TypeError):
            buggy()

    def test_no_fallback_for_value_error(self):
        @with_fallback(default="fallback")
        def buggy():
            raise ValueError("bad value")

        with pytest.raises(ValueError):
            buggy()

    def test_no_fallback_for_key_error(self):
        @with_fallback(default="fallback")
        def buggy():
            raise KeyError("missing")

        with pytest.raises(KeyError):
            buggy()

    def test_preserves_function_name(self):
        @with_fallback(default=None)
        def my_function():
            return 42

        assert my_function.__name__ == "my_function"
