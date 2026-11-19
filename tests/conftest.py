"""Without the MiniDev download (as in CI), tests that read it skip instead of failing.

`make data` downloads it; then every test runs. Tests that need the LLM-built indexes or
profiles have their own skipif.
"""

import pytest

from birdeval.sqlexec import DATA_ROOT

HAVE_DATA = (DATA_ROOT / "mini_dev_sqlite.json").exists()

# These modules read MiniDev at import time.
collect_ignore = [] if HAVE_DATA else ["test_fewshot.py", "test_schema.py", "test_sqlexec_and_llm.py"]


def pytest_configure(config):
    config.addinivalue_line("markers", "needs_data: reads the MiniDev questions or databases")


def pytest_collection_modifyitems(items):
    if HAVE_DATA:
        return
    skip = pytest.mark.skip(reason="MiniDev not downloaded (make data)")
    for item in items:
        if "needs_data" in item.keywords:
            item.add_marker(skip)
