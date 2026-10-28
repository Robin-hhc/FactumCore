"""Isolated mechanism fixture using only installed-package public CLI boundaries.

Independent review declarations are synthetic fixture data, not production semantic acceptance.
"""

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import yaml


REPO = Path(__file__).resolve().parents[2]
PUBLIC_SKILLS = tuple("hs-knowledge-" + name for name in (
    "apply", "change-plan", "explore", "lint", "maintain", "query",
    "source-prepare", "source-scan", "view-materialize"))
RETIRED_SKILLS = tuple("hs-knowledge-" + name for name in (
    "candidate-inspect", "candidate-revise", "governance-handoff", "index-build", "local-check",
    "merge-check", "publish-handoff", "query-regression", "recover", "source-capture"))


def install_packages(destination):
    """Install only the target distributable set; retired directories are absent."""
    destination.mkdir(parents=True)
    source = REPO / "skills/common/knowledge"
    for name in PUBLIC_SKILLS:
        shutil.copytree(source / name, destination / name,
                        ignore=shutil.ignore_patterns("tests", "__pycache__", "config.env", ".env"))
    assert {path.name for path in destination.iterdir()} == set(PUBLIC_SKILLS)
    assert not any((destination / name).exists() for name in RETIRED_SKILLS)
    return destination


def target_call(slug, request, action=None):
    """Migrate historical scenario labels to actual target public entries.

    Responses are never rewritten, and no retired package is loaded or called.
    This adapter is test infrastructure, not a runtime compatibility capability.
    """
    if slug in {"knowledge-source-capture", "source-capture"}:
        return "knowledge-source-prepare", request, "capture" if action in (None, "run") else action
    if slug in {"knowledge-source-scan", "source-scan"} and action == "prepare":
        return "knowledge-source-prepare", request, "prepare"
    if slug in {"knowledge-index-build", "index-build"}:
        return "knowledge-apply", request, "index-" + ("build" if action in (None, "run") else action)
    if slug in {"knowledge-query-regression", "query-regression"}:
        return "knowledge-apply", request, "regression-verify" if action == "verify" else "regression"
    if slug in {"knowledge-recover", "recover"}:
        return "knowledge-apply", request, action or request.get("mode", "inspect")
    if slug in {"knowledge-publish-handoff", "publish-handoff"}:
        return "knowledge-apply", request, "verify-submission" if action == "verify-submission" else "prepare-submission"
    if slug in {"knowledge-local-check", "local-check", "knowledge-merge-check", "merge-check"}:
        name = "verify-evidence" if action == "verify-proof" else "code-recheck" if action == "merge" or "merge-check" in slug else "code-check"
        return "knowledge-lint", request, name
    return slug, request, action


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def package_digest(package):
    files = {}
    for path in sorted(package.rglob("*")):
        rel = path.relative_to(package)
        if not path.is_file() or "tests" in rel.parts or "__pycache__" in rel.parts:
            continue
        if (
            rel.as_posix() == "SKILL.md"
            or rel.parts[0] in ("scripts", "references", "artifacts")
            or len(rel.parts) == 1
            and path.name.startswith("requirements")
            and path.suffix == ".txt"
        ):
            files[rel.as_posix()] = sha(path.read_bytes())
    return sha(canonical(files))


class Pipeline:
    def __init__(self, base):
        self.base, self.root = base, base / "w/himate-knowledge-wifi-mp"
        self.root.mkdir(parents=True)
        shutil.copytree(
            REPO / "himate-knowledge-wifi-mp/governance",
            self.root / "governance",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        self.rules = sha((self.root / "governance/framework.lock.yaml").read_bytes())
        self.root.joinpath(".isolated-knowledge-fixture").write_text("HIMATE_SYNTHETIC_FIXTURE_V2", encoding="utf-8")
        self.skills = install_packages(base / "installed-skills")
        self.catalog = {
            "schema_version": "2.0", "skills": {}, "test_fixture_root": str(self.root),
        }
        for package in self.skills.glob("hs-*"):
            if (package / "scripts/cli.py").is_file():
                self.catalog["skills"][package.name] = {
                    "root": str(package),
                    "entry": "scripts/cli.py",
                    "python": sys.executable,
                    "package_digest": package_digest(package),
                }
        self.catalog_path = base / "catalog.json"
        self.catalog_path.write_bytes(canonical(self.catalog))
        self.sequence = 0

    def write(self, ref, data):
        path = self.root / ref
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return ref

    def record(self, ref):
        import os
        path = str((self.root / ref).absolute())
        if os.name == "nt" and not path.startswith("\\\\?\\"):
            path = "\\\\?\\UNC\\" + path[2:] if path.startswith("\\\\") else "\\\\?\\" + path
        return json.loads(Path(path).read_bytes())

    def call(self, slug, request, action=None, expected=0):
        slug, request, action = target_call(slug, request, action)
        self.sequence += 1
        incoming, outgoing = self.base / f"input-{self.sequence}.json", self.base / f"output-{self.sequence}.json"
        incoming.write_bytes(canonical(request))
        argv = [
            sys.executable,
            str(self.skills / ("hs-" + slug) / "scripts/cli.py"),
            "--input",
            str(incoming),
            "--output",
            str(outgoing),
            "--knowledge-root",
            str(self.root),
            "--rules-digest",
            self.rules,
            "--catalog",
            str(self.catalog_path),
        ]
        if action:
            argv += ["--action", action]
        completed = subprocess.run(argv, capture_output=True, timeout=180)
        result = json.loads(outgoing.read_bytes()) if outgoing.exists() else {}
        assert completed.returncode == expected, (slug, result, completed.stderr.decode(errors="replace"))
        assert result.get("digest") == sha(
            canonical({key: value for key, value in result.items() if key != "digest"})
        ), result
        return result

    def capture(self, op, text, source_id="raw-source"):
        ref = self.write("docs-raw/specs/" + source_id + ".md", text)
        scan_ref = self.call("knowledge-source-scan", {"operation_id": op, "source": ref}, "scan")["data"]["scan_ref"]
        material_ref = self.call("knowledge-source-prepare", {"operation_id": op, "scan_ref": scan_ref},
                                 "prepare")["data"]["material_ref"]
        material = self.record(material_ref)
        if not hasattr(self, "prepared"):
            self.prepared = {}
        self.prepared[op] = {"scan_ref": scan_ref, "material_ref": material_ref, "bundle_ref": material["bundle_ref"]}
        return material["bundle_ref"], self.record(material["bundle_ref"])

    def card(self, card_id, bundle, text="Capture marker is an explicit synthetic rule.", relations=None):
        snapshot = bundle["snapshots"][0]
        template = (self.root / "governance/templates/rule.md").read_text(encoding="utf-8")
        for key, value in {
            "card_id": card_id,
            "title": card_id,
            "summary": "Isolated capture marker rule",
            "owner": "fixture",
            "evidence_ref": "e1",
            "source_id": snapshot["source_id"],
            "snapshot_id": snapshot["snapshot_id"],
            "claim_id": "c1",
            "claim_text": text,
        }.items():
            template = template.replace("{{" + key + "}}", value)
        _, front, body = template.split("---", 2)
        metadata = yaml.safe_load(front)
        metadata["scope"] = {"applicability": "universal", "contexts": []}
        metadata["claims"][0]["usage"] = "current"
        metadata["sources"][0]["locator"] = {"kind": "lines", "start": 1, "end": 2}
        metadata["relations"] = relations or []
        return ("---\n" + yaml.safe_dump(metadata, allow_unicode=True, sort_keys=False) + "---" + body).encode()

    def view(self, op, bundle_ref, card_id, card_bytes, decision="create", *,
             scan_ref=None, material_ref=None, queries=None, semantic=True):
        candidate = self.write(f".build/candidates/{op}/{card_id}.md", card_bytes)
        change = {
            "candidate_id": card_id,
            "decision": decision,
            "reason": "Synthetic pipeline acceptance",
            "card_inputs": [candidate],
        }
        request = {"operation_id": op, "bundle_ref": bundle_ref, "decisions": [change]}
        if semantic:
            bundle = self.record(bundle_ref)
            prepared = getattr(self, "prepared", {}).get(op, {})
            if prepared.get("bundle_ref") == bundle_ref:
                scan_ref = scan_ref or prepared["scan_ref"]
                material_ref = material_ref or prepared["material_ref"]
            sources = [row for row in bundle["resources"] if row.get("kind") == "raw"]
            if not sources:
                raise ValueError("Code-only independent byte fixtures must explicitly use semantic=False")
            if scan_ref is None:
                scan_ref = self.call("knowledge-source-scan", {"operation_id": op,
                    "source": sources[0]["path"]}, "scan")["data"]["scan_ref"]
            scan = self.record(scan_ref)
            if material_ref is None:
                material_ref = self.call("knowledge-source-prepare", {"operation_id": op,
                    "scan_ref": scan_ref, "unit_ids": [row["unit_id"] for row in scan["units"]],
                    "candidate_card_ids": [card_id] if decision == "update" else []}, "prepare")["data"]["material_ref"]
            material = self.record(material_ref)
            request["bundle_ref"] = material["bundle_ref"]
            _, front, _ = card_bytes.decode("utf-8-sig").split("---", 2)
            metadata = yaml.safe_load(front)
            unit_ids = [row["unit_id"] for row in scan["units"]]
            maintenance = [{"unit_id": "maintenance:" + row["card_id"] + "#" + row["claim_id"],
                "card_id": row["card_id"], "claim_id": row["claim_id"], "outcome": "content",
                "reason": "Fixture explicitly rechecks this affected Claim"}
                for row in scan.get("current_context", {}).get("affected_claims", [])]
            unit_ids += [row["unit_id"] for row in maintenance]
            cases = queries if queries is not None else [{"id": card_id, "query": card_id.replace("-", " "),
                "purpose": metadata["claims"][0].get("usage", "current"), "required": [card_id],
                "expected_claim_ids": [card_id + "#" + row["id"] for row in metadata["claims"]]}]
            semantic_ref = self.call("knowledge-change-plan", {"operation_id": op,
                "scan_ref": scan_ref, "material_ref": material_ref, "author_id": "fixture-author",
                "units": [{"unit_id": row["unit_id"], "outcome": "content", "reason": "Explicit synthetic source judgment"}
                          for row in scan["units"]], "maintenance_units": maintenance,
                "claim_changes": [{"unit_ids": unit_ids, "card_id": card_id, "claim_id": row["id"],
                    "action": decision, "before": "Previous synthetic assertion" if decision == "update" else None,
                    "after": "The explicitly authored fixture assertion", "conditions": "Fixture scope only",
                    "evidence": [{"source": source["snapshot_id"], "locator": "actual fixture locator"}
                                 for source in self.record(material["bundle_ref"])["snapshots"]],
                    "preserved": "Unchanged fixture scope", "reason": "Explicit fixture authored decision"}
                    for row in metadata["claims"]],
                "card_actions": [{"card_id": card_id, "decision": decision, "author_id": "fixture-author",
                                  "unit_ids": unit_ids, "reason": "Explicit fixture authored card decision"}],
                "target_queries": cases}, "plan")["data"]["semantic_plan_ref"]
            request.update(semantic_plan_ref=semantic_ref, material_ref=material_ref)
        materialized = self.call("knowledge-view-materialize", request, "run")
        return materialized["data"]["view_ref"]

    def review(self, op, view_ref):
        view = self.record(view_ref)
        semantic = self.record(view["semantic_plan_ref"])
        units = semantic["units"] + semantic.get("maintenance_units", [])
        material = self.record(view["material_ref"])
        historical = {row["card_digest"]: str(self.root / row["card_ref"])
                      for row in material.get("candidates", []) if row.get("card_ref")}
        result = self.call("knowledge-lint", {"operation_id": op, "view_ref": view_ref,
            "semantic_plan_ref": view["semantic_plan_ref"], "reviewer_id": "fixture-independent-reader",
            "independent_context": "fresh-fixture-context", "sampled_unit_ids": [row["unit_id"] for row in units],
            "unreviewed_unit_ids": [],
            "reason": "Fixture reader explicitly reviewed the entire selected scope", "findings": [],
            "inputs": {"historical_card_objects": historical}}, "review")
        ref = result["data"]["content_review_ref"]
        return ref, self.record(ref)

    def apply(self, op, view_ref):
        _, review = self.review(op, view_ref)
        record_ref = self.pending_record(op, view_ref)
        applied = self.call("knowledge-apply", {"operation_id": op, "view_ref": view_ref,
            "ingest_record_ref": record_ref}, "batch")
        return applied["data"]["apply_result_ref"], review

    def pending_record(self, op, view_ref):
        view = self.record(view_ref)
        pending = self.call("knowledge-source-scan", {"operation_id": op, "scan_ref": view["scan_ref"],
            "view_ref": view_ref, "disposition_preview_ref": view["disposition_preview_ref"]}, "record")
        return pending["data"]["ingest_record_ref"]
