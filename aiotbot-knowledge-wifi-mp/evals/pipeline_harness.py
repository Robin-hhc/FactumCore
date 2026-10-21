"""Isolated mechanism fixture using only installed-package public CLI boundaries.

Keys are generated per fixture and never represent a real human/host approval.
"""

import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

import yaml
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat


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
        self.key = Ed25519PrivateKey.generate()
        self.catalog = {
            "schema_version": "2.0",
            "skills": {},
            "review_trust": {
                "adapters": {
                    "fixture": {
                        "synthetic": True,
                        "fixture_root": str(self.root),
                        "public_key_b64": base64.b64encode(
                            self.key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
                        ).decode(),
                    }
                }
            },
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
        return json.loads((self.root / ref).read_bytes())

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

    def approve(self, op, view_ref):
        prepared = self.call("knowledge-confirmation-prepare", {"operation_id": op, "view_ref": view_ref})
        display_ref = prepared["data"]["display_ref"]
        display = self.record(display_ref)
        self.call("knowledge-confirmation-record", {"operation_id": op, "display_ref": display_ref}, expected=3)
        payload = {
            "actor_type": "human",
            "actor_id": "fixture-human",
            "decision": "approve",
            "display_digest": display["digest"],
            "view_digest": display["view_digest"],
            "challenge": display["challenge"],
            "issued_at": time.time(),
        }
        event = {
            "schema_version": "2.0",
            "record_kind": "host_event",
            "adapter_id": "fixture",
            "payload": payload,
            "signature_b64": base64.b64encode(self.key.sign(canonical(payload))).decode(),
        }
        event_ref = self.write(f".build/operations/{op}/host-event.json", canonical(event))
        reviewed = self.call(
            "knowledge-confirmation-record",
            {"operation_id": op, "display_ref": display_ref, "host_event_ref": event_ref},
        )
        return reviewed["data"]["manual_review_ref"], display

    def apply(self, op, view_ref):
        proof, display = self.approve(op, view_ref)
        applied = self.call("knowledge-apply", {"operation_id": op, "view_ref": view_ref, "proof_ref": proof})
        return applied["data"]["apply_result_ref"], display
