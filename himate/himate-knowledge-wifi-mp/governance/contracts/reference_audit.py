"""Explicit read-only code-reference audit. Never repairs or advances state."""
from __future__ import annotations

import difflib
import os
from pathlib import Path, PurePosixPath
import stat

from .runtime import NodeError, digest, fixed_bytes, load_yaml, read_json, safe, sha, write_bytes

MAX_TEXT_BYTES = 262144
MAX_FRAGMENT_LINES, MAX_FRAGMENT_CHARS = 20, 4096
MAX_DIFF_LINES, MAX_DIFF_CHARS = 60, 8192


def excerpt(text, max_lines, max_chars):
    lines = text.splitlines(keepends=True)
    selected = "".join(lines[:max_lines])[:max_chars]
    return selected, len(selected) < len(text)


def issue(code, reason, **location):
    return {"code": code, "reason": str(reason), **location}


def formal_snapshot(context):
    view = context.modules["checks"].prepare_view(context.root)
    return view, digest({ref: sha(raw) for ref, raw in view["files"].items()})


def fixed_report(context, files_digest):
    reference = context.request.get("lint_report_ref")
    if not reference:
        return None, [issue("LINT_REPORT_NOT_PROVIDED", "No fixed-check report was supplied; fixed checks were not run by this action")]
    try:
        path = safe(context.root, reference, [".build", "logs", "artifacts"])
        report = read_json(path)
        context.modules["checks"].validate_report(report, expected_rules=context.args.rules_digest, required_scope="full")
        if report.get("mode") != "formal" or Path(report.get("object", {}).get("root", "")).resolve() != context.root:
            raise NodeError("LINT_REPORT_OBJECT_MISMATCH", "Expected a formal full-library report for this exact knowledge root")
        if report["object"].get("files_digest") != files_digest:
            return report, [issue("LINT_REPORT_SNAPSHOT_MISMATCH", "The saved report does not bind the current formal file set; keep its original observation time", path=reference)]
        return report, []
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return None, [issue("LINT_REPORT_UNAVAILABLE", exc, path=str(reference))]


def configuration(context):
    v = context.modules["validation"]
    path = v.workspace_config_path(context.root)
    raw = fixed_bytes(path.parent, path.name)
    declared = load_yaml(raw)
    v.validate_shape("workspace", declared, context.rules)
    config = v.normalize_workspace(declared, path.parent)
    return {"path": path, "raw": raw, "sha256": sha(raw), "config": config}


def unlinked_root(path):
    """Reject root/ancestor links before any selected code bytes are read."""
    for item in [path, *path.parents]:
        if item.is_symlink() or (os.path.lexists(item) and getattr(item.lstat(), "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise NodeError("CODE_PATH_UNAUTHORIZED", "Linked code root is not permitted", path)
    return path.resolve(strict=True)


def current_source(context, config_state, resource):
    """Observe only an authorized configured file; absence differs from IO gaps."""
    if config_state is None:
        return {"observation": "unavailable", "current_sha256": None, "gap": issue("CODE_CONFIG_UNAVAILABLE", "Cannot authorize a current code file without the actual workspace configuration")}
    try:
        config = config_state["config"]
        repo_id, relative = resource["repo_id"], resource["path"]
        if {part.casefold() for part in PurePosixPath(relative).parts} & {".git", ".repo", ".hg", ".svn"}:
            raise NodeError("CODE_PATH_UNAUTHORIZED", "Repository-manager internals are outside code audit scope", relative)
        mappings = [row for row in config["repos"] if row["repo_id"] == repo_id]
        if len(mappings) != 1 or not context.modules["validation"].workspace_file_allowed(config, repo_id, relative):
            raise NodeError("CODE_PATH_UNAUTHORIZED", "Reference is outside the actual configured module range", relative)
        mapping = mappings[0]
        root = Path(mapping["root"])
        if not root.is_absolute():
            root = config_state["path"].parent / root
        protected = config.get("code_policy", {}).get("repo_roots", {}).get(repo_id)
        if not protected or not Path(protected).is_absolute() or root.resolve() != Path(protected).resolve():
            raise NodeError("CODE_PATH_UNAUTHORIZED", "Configured repository does not match its actual authorized root", relative)
        root = unlinked_root(root)
        path = safe(root, relative)
        before = path.stat()
        if not stat.S_ISREG(before.st_mode):
            raise NodeError("CODE_FILE_UNREADABLE", "Selected code location is not a regular file", relative)
        raw = fixed_bytes(root, relative)
        after = safe(root, relative).stat()
        def signature(value):
            return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns
        if signature(before) != signature(after) or fixed_bytes(config_state["path"].parent, config_state["path"].name) != config_state["raw"]:
            raise NodeError("CODE_CHANGED_DURING_AUDIT", "Code or its configuration changed while being observed", relative)
        return {"observation": "available", "current_sha256": sha(raw), "raw": raw, "root": root, "relative": relative, "signature": signature(after)}
    except FileNotFoundError as exc:
        if not config_state["path"].is_file():
            return {"observation": "unavailable", "current_sha256": None, "gap": issue("CODE_CONFIG_UNAVAILABLE", exc)}
        return {"observation": "missing", "current_sha256": None}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"observation": "unavailable", "current_sha256": None, "gap": issue(getattr(exc, "code", "CODE_FILE_UNREADABLE"), exc)}


def effect_for(claims, changed, navigation=None):
    usages = {row["usage"] for row in claims}
    if usages == {"historical"}:
        return "historical_reference"
    if navigation is not None and "current" not in usages:
        if navigation.get("status") == "resolved":
            return "guidance_navigation_resolved" if "guidance" in usages else "unadopted_navigation_resolved"
        return "guidance_navigation_needs_review" if "guidance" in usages else "unadopted_reference_needs_review"
    if not changed:
        return "unchanged_reference"
    if "current" in usages:
        return "current_reference_needs_review"
    if "guidance" in usages:
        return "guidance_navigation_needs_review"
    return "unadopted_reference_needs_review"


def reference_row(context, card, reference, resource, lock, config_state, observed):
    claims = [{"claim_id": claim["id"], "usage": claim["usage"]} for claim in card["metadata"]["claims"] if reference["evidence_ref"] in claim["source_refs"]]
    row = {"card_path": card["path"], "card_id": card["metadata"]["id"], "card_sha256": card["sha256"],
           "claim_ids": [claim["claim_id"] for claim in claims], "claims": claims,
           **{key: reference[key] for key in ("evidence_ref", "source_id", "snapshot_id")},
           "repo_id": resource["repo_id"], "path": resource["path"], "old_locator": reference["locator"],
           "old_sha256": None, "old_fragment": None, "old_fragment_truncated": False, "diff_truncated": False,
           "content_omitted_reason": None, "current_sha256": observed["current_sha256"],
           "current_source_matches": None, "observation": observed["observation"], "gaps": [], "difference": "", "suggestion": ""}
    if observed.get("gap"):
        row["gaps"].append(observed["gap"])
    try:
        snapshot = context.modules["source_resources"].validate_source_ref(reference, lock)
        row["old_sha256"] = snapshot["sha256"]
        large_file = max(snapshot["bytes"], len(observed.get("raw", b""))) > MAX_TEXT_BYTES
        if observed["observation"] == "available":
            row["current_source_matches"] = observed["current_sha256"] == snapshot["sha256"] and len(observed["raw"]) == snapshot["bytes"]
            row["observation"] = "unchanged" if row["current_source_matches"] else "changed"
            if not row["current_source_matches"]:
                row["difference"] = "Whole-file bytes differ; the old locator is historical and is not automatically relocated."
                if not large_file:
                    old_raw = context.modules["source_resources"].recover_snapshot(context.root, snapshot)
                    adapter = (snapshot.get("extraction") or {}).get("extractor")
                    try:
                        old_text, _ = context.modules["source_resources"].extract_code_text(old_raw, adapter)
                        current_text, _ = context.modules["source_resources"].extract_code_text(observed["raw"], adapter)
                        changes = "".join(difflib.unified_diff(old_text.splitlines(True), current_text.splitlines(True), fromfile="adopted/" + resource["path"], tofile="current/" + resource["path"]))
                        selected, row["diff_truncated"] = excerpt(changes, MAX_DIFF_LINES, MAX_DIFF_CHARS)
                        row["difference"] += "\n" + selected
                    except (ValueError, UnicodeError):
                        row["difference"] += " Text diff is unavailable under the declared code adapter."
        elif observed["observation"] == "missing":
            row["current_source_matches"] = False
            row["difference"] = "The authorized current file is missing; the old locator remains a historical address."
        if large_file:
            context.modules["source_resources"].recover_snapshot(context.root, snapshot)
            row.update(old_fragment_truncated=True, diff_truncated=True, content_omitted_reason="Code file exceeds the 256 KiB text-audit limit; only exact hashes and the old locator are reported.")
        else:
            resolved = context.modules["source_operations"].resolve_source(context, ({'operation_id': context.operation, 'source_ref': reference})["source_ref"])
            if resolved.get("text") is None:
                row["gaps"].append(issue("OLD_FRAGMENT_UNAVAILABLE", "Exact old text extraction is unavailable; the snapshot hash is retained"))
            else:
                row["old_fragment"], row["old_fragment_truncated"] = excerpt(resolved["text"], MAX_FRAGMENT_LINES, MAX_FRAGMENT_CHARS)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        row["gaps"].append(issue("ADOPTED_CODE_UNAVAILABLE", exc))
    if "code_ref" in reference:
        row["code_ref"] = reference["code_ref"]
        try:
            row["code_navigation"] = context.modules["source_resources"].resolve_code_navigation(
                context.root, reference, lock,
                cache=context.modules["source_operations"].symbol_cache(context),
            )
        except (OSError, ValueError, KeyError, TypeError) as exc:
            row["code_navigation"] = {"status": "unavailable", "code": "CODE_NAVIGATION_UNAVAILABLE",
                                      "reason": str(exc), "path": resource["path"], "matches": []}
        if row["code_navigation"]["status"] == "unavailable":
            row["gaps"].append(issue(row["code_navigation"]["code"], row["code_navigation"]["reason"]))
    changed = row["current_source_matches"] is not True
    row["effect"] = effect_for(claims, changed, row.get("code_navigation"))
    row["suggestion"] = {
        "historical_reference": "Keep the fixed historical purpose; current-file drift alone does not invalidate this historical Claim.",
        "current_reference_needs_review": "Ask ingest to read the actual current implementation, assess the Claim and update or narrow its evidence and scope.",
        "guidance_navigation_needs_review": "Review this code-navigation reference through ingest; do not infer that the guidance content is false.",
        "guidance_navigation_resolved": "The declared current symbol remains uniquely navigable; retain the fixed document guidance and its historical evidence.",
        "unadopted_navigation_resolved": "The metadata-only symbol remains uniquely navigable; no Claim adopts this reference.",
        "unadopted_reference_needs_review": "Review this metadata-only code reference through ingest; no Claim currently adopts it.",
        "unchanged_reference": "Reference bytes match; this mechanical observation does not establish semantic support.",
    }[row["effect"]]
    return row


def markdown(payload, audit_ref):
    lines = ["# 代码引用巡检报告", "", f"状态：{payload['status']}；检查完整：{payload['complete']}。", "",
             f"结构化依据：`{audit_ref}`；规则：`{payload['rules_digest']}`。", "",
             "本次仅观察正式卡、采用来源和实际代码；报告不修改引用，不判断代码是否支持知识结论。", "",
             "## 固定检查结果", ""]
    fixed = payload.get("lint_report")
    if fixed:
        lines += [f"原报告：`{payload['lint_report_ref']}`；状态：`{fixed['status']}`；摘要：`{fixed['digest']}`。", ""]
        for check in fixed["checks"]:
            lines.append(f"- `{check['check_id']}`：{check['status']}")
        for finding in fixed["findings"]:
            lines.append(f"- `{finding['code']}` `{finding['path']}`：{finding['reason']}")
    else:
        lines.append("未取得可接受的固定检查报告；本动作没有代跑固定检查。")
    lines += ["", "## 代码引用", ""]
    if not payload["references"]:
        lines.append("本次可解析的正式卡中没有代码来源引用；解析及覆盖缺口见下文。")
    for row in payload["references"]:
        lines += [f"### {row['card_id']} / {row['evidence_ref']}", "",
                  f"位置：`{row['card_path']}`；卡指纹：`{row['card_sha256']}`。", "",
                  f"Claim／用途：`{row['claims']}`；未采用引用：{not row['claims']}。", "",
                  f"代码：`{row['repo_id']}:{row['path']}`；旧定位：`{row['old_locator']}`。", "",
                  f"来源／快照：`{row['source_id']}` / `{row['snapshot_id']}`。", "",
                  f"旧 hash：`{row['old_sha256']}`；当前 hash：`{row['current_sha256']}`。", "",
                  f"观察：`{row['observation']}`；匹配：`{row['current_source_matches']}`；用途判断：`{row['effect']}`。", ""]
        if row.get("code_navigation"):
            navigation = row["code_navigation"]
            position = navigation.get("path") or row["path"]
            if navigation.get("range"):
                position += f"#L{navigation['range']['start_line']}-L{navigation['range']['end_line']}"
            lines += [f"当前符号导航：`{navigation['status']}`；位置：`{position}`。{navigation['reason']}", ""]
        if row["old_fragment"] is not None:
            lines += ["旧片段：", "", *["> " + line for line in row["old_fragment"].splitlines()], ""]
        if row["difference"]:
            lines += ["差异：", "", *["> " + line for line in row["difference"].splitlines()], ""]
        if row["old_fragment_truncated"] or row["diff_truncated"]:
            lines += [f"显示限制：旧片段截断={row['old_fragment_truncated']}；差异截断={row['diff_truncated']}。省略部分不表示没有变化。", ""]
        if row["content_omitted_reason"]:
            lines += [row["content_omitted_reason"], ""]
        lines += [row["suggestion"], ""]
        for gap in row["gaps"]:
            lines.append(f"- 缺口 `{gap['code']}`：{gap['reason']}")
    lines += ["", "## 覆盖与缺口", "", f"统计：`{payload['counts']}`。", ""]
    for gap in payload["gaps"]:
        lines.append(f"- `{gap['code']}` `{gap.get('path', '')}`：{gap['reason']}")
    affected = sorted({row["card_path"] for row in payload["references"] if row["effect"].endswith("needs_review")})
    lines += ["", "## 手动转入 ingest 的提示词", "", "> 请使用 knowledge ingest，读取以下巡检依据，先核对当前文件和报告时点，再只修订待复核卡及固定检查实际指出的对象和必要依赖；不要重新提炼所有 raw。", f"> 结构化报告：{audit_ref}", f"> 引用待复核卡：{', '.join(affected) if affected else '本次没有可确定的引用待复核卡，先处理报告明确列出的固定检查问题和缺口。'}", "> 逐 Claim 阅读当前源码，判断结论、条件及引用如何修订；保留 historical 用途，guidance 变化先复核导航，不自动替换行号或 hash。", "> 缺材料时明确记录缺口；修订后按现有 ingest 完成独立复核、检查、入库和检索验证。", ""]
    return "\n".join(lines).encode("utf-8")


def audit_references(context):
    gaps, rows, observed_files, differences = [], [], {}, {}
    try:
        view, files_digest = formal_snapshot(context)
    except (OSError, ValueError) as exc:
        view, files_digest = {"files": {}}, None
        gaps.append(issue("FORMAL_LIBRARY_UNAVAILABLE", exc))
    report, report_gaps = fixed_report(context, files_digest)
    gaps += report_gaps
    try:
        lock = context.modules["source_resources"].read_source_lock(context.root)
        context.modules["validation"].validate_shape("sources", lock, context.rules)
        resources = {row["source_id"]: row for row in lock["resources"]}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        lock, resources = {"snapshots": [], "resources": []}, {}
        gaps.append(issue("SOURCE_LOCK_UNAVAILABLE", exc))
    config_state = None
    code_references = []
    for path, raw in sorted(view["files"].items()):
        if not path.startswith("knowledge/") or not path.endswith(".md") or path.rsplit("/", 1)[-1] in {"index.md", "AGENTS.md", "README.md"}:
            continue
        try:
            card = context.modules["knowledge"].decode_card(raw, path, context.rules)
            for reference in card["metadata"]["sources"]:
                resource = resources.get(reference["source_id"])
                if resource is None:
                    gaps.append(issue("SOURCE_RESOURCE_UNAVAILABLE", "A formal card references an unregistered source", path=path, source_id=reference["source_id"]))
                elif resource.get("kind") == "code":
                    locator = reference["locator"]
                    effective = {**resource, "repo_id": locator.get("repo_id") or resource["repo_id"], "path": locator.get("path") or resource["path"]}
                    code_references.append((card, reference, effective))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            gaps.append(issue("FORMAL_CARD_UNREADABLE", exc, path=path))
    if code_references:
        try:
            config_state = configuration(context)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            gaps.append(issue("CODE_CONFIG_UNAVAILABLE", exc))
    for card, reference, resource in code_references:
        key = resource["repo_id"], resource["path"]
        if key not in observed_files:
            observed_files[key] = current_source(context, config_state, resource)
        row = reference_row(context, card, reference, resource, lock, config_state, observed_files[key])
        diff_key = (resource["repo_id"], resource["path"], row["old_sha256"], row["current_sha256"])
        if row["observation"] == "changed":
            if diff_key in differences:
                row["difference_ref"] = differences[diff_key]
                row["difference"] = "Whole-file bytes differ; the bounded text difference is already reported at " + row["difference_ref"]
            else:
                differences[diff_key] = row["card_path"] + "#" + row["evidence_ref"]
        rows.append(row)
    # Recheck observations at completion; the audit is not an atomic filesystem snapshot.
    for key, observed in observed_files.items():
        if observed["observation"] != "available":
            continue
        try:
            if sha(fixed_bytes(observed["root"], observed["relative"])) != observed["current_sha256"]:
                raise NodeError("CODE_CHANGED_DURING_AUDIT", "Current code changed before report completion")
        except (OSError, ValueError) as exc:
            gap = issue("CODE_CHANGED_DURING_AUDIT", exc, repo_id=key[0], path=key[1])
            gaps.append(gap)
            for row in rows:
                if (row["repo_id"], row["path"]) == key:
                    row.update(current_source_matches=None, observation="unstable", observed_sha256=row["current_sha256"], current_sha256=None,
                               effect=effect_for(row["claims"], True), suggestion="The source changed during this audit; read the actual current file again before any ingest decision. Historical evidence retains its historical purpose.")
                    row["gaps"].append(gap)
    try:
        _, after_digest = formal_snapshot(context)
        if after_digest != files_digest:
            gaps.append(issue("FORMAL_LIBRARY_CHANGED_DURING_AUDIT", "Formal library bytes changed during this observation"))
        if config_state and fixed_bytes(config_state["path"].parent, config_state["path"].name) != config_state["raw"]:
            gaps.append(issue("CODE_CONFIG_CHANGED_DURING_AUDIT", "Workspace configuration changed during this observation"))
    except (OSError, ValueError) as exc:
        gaps.append(issue("AUDIT_RECHECK_UNAVAILABLE", exc))
    complete = not gaps and all(not row["gaps"] for row in rows) and (report is not None and report.get("complete") is True)
    counts = {"code_references": len(rows), "changed": sum(row["observation"] == "changed" for row in rows),
              "missing": sum(row["observation"] == "missing" for row in rows), "unavailable": sum(row["observation"] in {"unavailable", "unstable"} for row in rows),
              "guidance": sum(any(claim["usage"] == "guidance" for claim in row["claims"]) for row in rows),
              "historical": sum(row["effect"] == "historical_reference" for row in rows), "unadopted": sum(not row["claims"] for row in rows)}
    needs_review = any(row["effect"].endswith("needs_review") for row in rows) or (report is not None and report["status"] == "failed")
    status = "incomplete" if not complete else "needs_review" if needs_review else "passed"
    payload = {"purpose": "code_reference_audit", "knowledge_root": str(context.root), "formal_files_digest": files_digest,
               "config_digest": config_state["sha256"] if config_state else None, "lint_report_ref": context.request.get("lint_report_ref"),
               "lint_report": report, "references": rows, "gaps": gaps, "counts": counts, "complete": complete, "status": status,
               "limits": ["Only declared formal-card code references were inspected; unrecorded semantic dependencies are outside this report.",
                          "A matching hash does not establish semantic support, runtime behavior or deployment acceptance.",
                          "Saved fixed checks and code observations are separate observations, not an atomic snapshot."]}
    artifact = context.seal(payload, "artifact_manifest")
    audit_ref, report_ref = context.base + "/code-reference-audit.json", context.base + "/code-reference-audit.md"
    context.save(audit_ref, artifact)
    write_bytes(context.root, report_ref, markdown(artifact, audit_ref))
    return {"audit_ref": audit_ref, "report_ref": report_ref, "complete": complete, "status": status, "counts": counts}, "reported"
