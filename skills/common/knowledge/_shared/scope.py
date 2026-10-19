"""Configuration and complete-condition matching; matching alone grants no proof eligibility."""

CHIPS = ("chip12", "chip08", "chip07c")
SIDES = ("host", "device")


def validate_configuration(config):
    diagnostics = []

    def error(code, message, path):
        diagnostics.append({"code": code, "message": message, "path": path})

    repos = config.get("repos", [])
    repo_ids = [r["repo_id"] for r in repos]
    if len(repo_ids) != len(set(repo_ids)):
        error("DUPLICATE_REPO", "Repository IDs must be unique", "/repos")
    roots = config.get("knowledge_roots", {})
    binding_ids = set()
    for i, binding in enumerate(config.get("architecture", [])):
        if binding["binding_id"] in binding_ids:
            error("DUPLICATE_BINDING", "Binding IDs must be unique", f"/architecture/{i}")
        binding_ids.add(binding["binding_id"])
        if binding["repo_id"] not in repo_ids:
            error(
                "SOURCE_REF_MISSING",
                "Binding references an unknown repository",
                f"/architecture/{i}",
            )
        if binding["knowledge_domain"] not in roots:
            error(
                "DOMAIN_REF_MISSING", "Binding references an unknown domain", f"/architecture/{i}"
            )
    targets = config.get("targets", [])
    target_ids = [t["target_id"] for t in targets]
    if len(target_ids) != len(set(target_ids)):
        error("DUPLICATE_TARGET", "Target IDs must be unique", "/targets")
    expected = {f"{chip}-{side}" for chip in CHIPS for side in SIDES}
    if set(target_ids) != expected:
        error("TARGET_SET_MISMATCH", "Expected six WiFi logical targets", "/targets")
    target_map = {t["target_id"]: t for t in targets}
    for i, target in enumerate(targets):
        if target["target_id"] != f"{target['chip']}-{target['side']}":
            error("TARGET_ID_MISMATCH", "Target ID disagrees with chip and side", f"/targets/{i}")
        for source in target.get("source_bindings", []):
            if source not in repo_ids:
                error("SOURCE_REF_MISSING", "Target source is not registered", f"/targets/{i}")
    pair_ids, paired_chips = set(), []
    for i, pair in enumerate(config.get("pairs", [])):
        if pair["pairing_id"] in pair_ids:
            error("DUPLICATE_PAIR", "Pair IDs must be unique", f"/pairs/{i}")
        pair_ids.add(pair["pairing_id"])
        host = target_map.get(pair["host_target"])
        device = target_map.get(pair["device_target"])
        if (
            not host
            or not device
            or host["side"] != "host"
            or device["side"] != "device"
            or host["chip"] != device["chip"]
        ):
            error("INVALID_PAIR", "Pair requires Host and Device of the same chip", f"/pairs/{i}")
        else:
            paired_chips.append(host["chip"])
    if sorted(paired_chips) != sorted(CHIPS):
        error("PAIR_SET_MISMATCH", "Expected one pair per chip", "/pairs")
    query = config.get("query", {})
    if query.get("default_channel") not in query.get("allowed_channels", []):
        error("INVALID_DEFAULT_CHANNEL", "Default channel must be allowed", "/query")
    return diagnostics


def unknown_targets(config):
    repos = {r["repo_id"]: r for r in config["repos"]}
    return sorted(
        t["target_id"]
        for t in config["targets"]
        if (
            not t.get("source_bindings")
            or t.get("build_profile") is None
            or any(not repos.get(source, {}).get("root") for source in t["source_bindings"])
        )
    )


def evaluate_conditions(scope, context):
    applicability = scope.get("applicability", "unknown")
    if applicability == "unknown":
        return {"status": "unknown", "reasons": ["applicability_unknown"]}
    if applicability == "universal":
        return {"status": "match", "reasons": ["declared_universal_not_a_verification"]}
    groups = scope.get("contexts", [])
    if not groups:
        return {"status": "unknown", "reasons": ["no_condition_groups"]}
    results = []
    for group in groups:
        mismatch, missing = [], []
        # Snapshot proof is supplied by later source/gate modules, not guessed
        # from a declaration's policy name or a caller's current revision.
        if group.get("revision_policy") in {"pinned", "revalidate"}:
            missing.append("snapshot_proof")
        for key in ("target_id", "chip", "side", "build_profile", "revision"):
            if key not in group:
                continue
            if group[key] is None or context.get(key) is None:
                missing.append(key)
            elif group[key] != context[key]:
                mismatch.append(key)
        for expected_field, context_field, exclude in (
            ("features_all", "features", False),
            ("features_none", "features", True),
            ("protocol_versions", "protocol_versions", False),
        ):
            expected = group.get(expected_field, [])
            if expected:
                if context.get(context_field) is None:
                    missing.append(context_field)
                else:
                    wanted, actual = set(expected), set(context[context_field])
                    if bool(wanted & actual) if exclude else not wanted <= actual:
                        mismatch.append(expected_field)
        status = "mismatch" if mismatch else ("unknown" if missing else "match")
        results.append(
            {
                "context_id": group.get("context_id"),
                "status": status,
                "mismatch": mismatch,
                "missing": missing,
            }
        )
    status = (
        "match"
        if any(g["status"] == "match" for g in results)
        else "unknown"
        if any(g["status"] == "unknown" for g in results)
        else "mismatch"
    )
    return {"status": status, "groups": results}
