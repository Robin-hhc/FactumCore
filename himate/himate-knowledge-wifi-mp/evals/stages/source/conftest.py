"""Behavioral cases; shared synthetic materials live under evals/support."""

import pytest
from support.stages.source import (
    Harness,
)


@pytest.fixture
def harness(tmp_path):
    return Harness(tmp_path)


@pytest.fixture
def planned_flow(harness):
    from support.stages.source_flow import planned_flow as build_flow
    return build_flow(harness)
