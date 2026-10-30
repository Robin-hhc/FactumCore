"""Register shared stage fixtures without importing another test module."""

from support.stages.apply_formats import (
    pipeline as pipeline,
    release_runtime as release_runtime,
)
from support.stages.apply_publication import publication_case as publication_case
