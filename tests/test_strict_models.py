"""Strict models only when CODEXED_STRICT_MODELS=1, not whenever pytest is imported."""

from __future__ import annotations

import os
import subprocess
import sys


def _is_dev(env: dict[str, str]) -> str:
    code = "import pytest, codexed.models.base as b; print(b.IS_DEV)"
    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def test_pytest_import_alone_does_not_make_models_strict() -> None:
    env = {k: v for k, v in os.environ.items() if k != "CODEXED_STRICT_MODELS"}
    assert _is_dev(env) == "False"
    assert _is_dev({**env, "CODEXED_STRICT_MODELS": "1"}) == "True"
