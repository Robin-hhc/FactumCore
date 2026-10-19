"""Domain adapters to the one shared implementation; no second validation engine."""


def validate_shape(record, knowledge_root):
    from _shared.contracts import validate_document

    return validate_document("record", record, knowledge_root)


def validate_confirmation(knowledge_root, operation_id, review_ref):
    from _shared.changes import validate_review

    return validate_review(knowledge_root, operation_id, review_ref)
