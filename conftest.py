import os
import tempfile
import time

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Use a unique per-session basetemp unless one was given explicitly.

    On some systems a stale temp dir (e.g. Windows with an antivirus holding
    handles to ``pytest-of-<user>``) cannot be scanned or removed, which breaks
    the tmp_path fixture setup. A fresh unique dir sidesteps that. CI
    checkouts are already clean, so this is harmless there.
    """
    if not getattr(config.option, "basetemp", None):
        base = os.path.join(
            tempfile.gettempdir(),
            f"bse-pytest-{os.getpid()}-{time.time_ns()}",
        )
        config.option.basetemp = base
