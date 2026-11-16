"""Pure domain contracts; importing performs no filesystem operations."""

from .validation import ContractError, load_rules, validate_shape

CONTRACT_FAMILY = "aiot-wifi"
CONTRACT_VERSION = "2.0"

__all__ = [
    "CONTRACT_FAMILY",
    "CONTRACT_VERSION",
    "ContractError",
    "load_rules",
    "validate_shape",
]
