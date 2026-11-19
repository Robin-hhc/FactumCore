"""Project explicit historical references while ordinary references stay current."""


MISSING_VERSION = {"SOURCE_INPUT_UNAVAILABLE", "GIT_SOURCE_UNAVAILABLE", "PATH_OUTSIDE_ALLOWED_ROOT",
                   "RECOVERY_CONFIG_REQUIRED", "RECOVERY_CONFIG_MISMATCH", "RECOVERY_REPO_UNKNOWN",
                   "RECOVERY_REPO_MISMATCH"}


def project_index(registry):
    return {row["snapshot_id"]: row for row in registry.get("snapshots", [])}


def project_reference(card, kind, reference, index):
    identity = reference[kind + "_id"]
    declared = reference.get("snapshot_id")
    if declared is None:
        return {**reference, "source_version": "current"}
    snapshot = index.get(declared)
    if snapshot and snapshot.get("source_id") == identity:
        return {**reference, "source_sha256": snapshot["sha256"], "source_version": "bound"}
    return {**reference, "source_version": "unavailable"}
