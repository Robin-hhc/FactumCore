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
        self.base, self.root = base, base / "w/aiotbot-knowledge-wifi-mp"
        self.root.mkdir(parents=True)
        shutil.copytree(
            REPO / "aiotbot-knowledge-wifi-mp/governance",
            self.root / "governance",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        self.rules = sha((self.root / "governance/framework.lock.yaml").read_bytes())
        self.root.joinpath(".isolated-knowledge-fixture").write_text("AIOTBOT_SYNTHETIC_FIXTURE_V2", encoding="utf-8")
        self.skills = REPO / "skills/common/knowledge"
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
        result = self.call("knowledge-source-capture", {"operation_id": op, "source_path": ref, "source_id": source_id})
        return result["data"]["bundle_ref"], self.record(result["data"]["bundle_ref"])

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

    def view(self, op, bundle_ref, card_id, card_bytes, decision="create"):
        candidate = self.write(f".build/candidates/{op}/{card_id}.md", card_bytes)
        change = {
            "candidate_id": card_id,
            "decision": decision,
            "reason": "Synthetic pipeline acceptance",
            "card_inputs": [candidate],
        }
        planned = self.call(
            "knowledge-change-plan", {"operation_id": op, "bundle_ref": bundle_ref, "decisions": [change]}
        )
        materialized = self.call(
            "knowledge-view-materialize", {"operation_id": op, "plan_ref": planned["data"]["plan_ref"]}
        )
        return materialized["data"]["view_ref"]

    def review(self, op, view_ref):
        view = self.record(view_ref)
        review = {
            "schema_version": "2.0", "record_kind": "content_review", "operation_id": op,
            "rules_digest": self.rules, "tool_identity": view["tool_identity"],
            "status": "passed", "view_digest": view["digest"],
            "plan_ref": view["plan_ref"], "plan_digest": view["plan_digest"],
            "author_id": "fixture-author", "reviewer_id": "fixture-independent-reader",
            "independent_context": "fresh-fixture-context", "findings": [],
            "verification_tier": "declared_independent_content_review",
        }
        review["digest"] = sha(canonical(review))
        ref = self.write(f".build/operations/{op}/content-review.json", canonical(review))
        return ref, review

    def apply(self, op, view_ref):
        proof, review = self.review(op, view_ref)
        applied = self.call("knowledge-apply", {"operation_id": op, "view_ref": view_ref,
                                               "content_review_ref": proof})
        return applied["data"]["apply_result_ref"], review
