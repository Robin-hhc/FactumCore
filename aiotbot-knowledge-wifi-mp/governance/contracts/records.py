"""Record integrity; a public digest seal never authenticates human consent."""

from .validation import ContractError, digest_payload, validate_shape


def seal(record):
    result = dict(record)
    result["digest"] = digest_payload(result)
    return result


def verify(record, expected=None):
    if not isinstance(record, dict) or record.get("digest") != digest_payload(record):
        raise ContractError("RECORD_DIGEST_MISMATCH", "Record fields changed")
    if record.get("schema_version") != "2.0":
        raise ContractError("UNSUPPORTED_RECORD_VERSION", "Expected 2.0")
    for field, value in (expected or {}).items():
        if record.get(field) != value:
            raise ContractError("RECORD_BINDING_MISMATCH", field)
    return record


def validate_record_shape(record, rules):
    return validate_shape("record", record, rules)


def validate_record_binding(record, expected):
    return verify(record, expected)
