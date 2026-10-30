"""Compatibility alias to the single repository command protocol."""
import sys
from ... import protocol as _protocol

globals().update({key: value for key, value in vars(_protocol).items() if not key.startswith("__")})
sys.modules[__name__] = _protocol
