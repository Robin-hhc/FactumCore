"""Behavioral cases; shared synthetic materials live under evals/support."""

import pytest
from support.stages.change_plan import (
    Harness,
)


@pytest.fixture
def harness(tmp_path):
    return Harness(tmp_path)
