"""Tests for PEP 810 lazy imports and v2_types leaf module isolation."""

import subprocess
import sys

import pytest

import codexed
import codexed.models


def test_all_public_exports_resolve() -> None:
    """Every symbol in ``codexed.__all__`` and ``codexed.models.__all__`` resolves."""
    for name in codexed.__all__:
        assert hasattr(codexed, name), f"codexed.{name} failed to resolve"
    for name in codexed.models.__all__:
        assert hasattr(codexed.models, name), f"codexed.models.{name} failed to resolve"


@pytest.mark.skipif(sys.version_info < (3, 15), reason="PEP 810 __lazy_modules__ requires 3.15+")
def test_scalar_type_import_skips_v2_protocol_client_and_mcp() -> None:
    """Importing scalar/Literal types on 3.15+ must not load v2_protocol, client, or mcp."""
    code = (
        "import sys\n"
        "from codexed import Personality, ReasoningEffort, SandboxMode\n"
        "assert 'codexed.models.v2_types' in sys.modules\n"
        "assert 'codexed.models.v2_protocol' not in sys.modules\n"
        "assert 'codexed.client' not in sys.modules\n"
        "assert 'mcp' not in sys.modules\n"
        "assert all(x is not None for x in (Personality, ReasoningEffort, SandboxMode))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
