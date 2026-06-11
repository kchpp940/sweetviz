"""
Pytest suite for sweetviz pre-release checks.

Run with:  pytest tests/pre_release -v
"""
from sweetviz._pre_release import ALL_CHECKS


def _make_pytest_func(func):
    def test_func():
        try:
            func()
        except Exception as exc:
            raise AssertionError(f"{type(exc).__name__}: {exc}") from exc
    test_func.__doc__ = func.__name__
    return test_func


for _name, _func in ALL_CHECKS:
    _tag = _name.replace(".", "_")
    globals()[f"test_prerelease_{_tag}"] = _make_pytest_func(_func)
