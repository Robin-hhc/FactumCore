"""Real Git consumers and interrupted-generation protection for synthetic dbox.

Set HIMATE_DBOX_RELEASE_CHECKOUT to exercise a read-only released source snapshot.
All executable packages are installed into each fixture; no real originals are read.
The authored statements and independent review declarations remain synthetic data.
"""

import base64 as base64
import copy as copy
import hashlib
import json
import os
from pathlib import Path
import shutil as shutil
import subprocess
import sys
import time

import pytest as pytest
import yaml

from support.releases import load_manual, select_release


REPO = Path(__file__).resolve().parents[5]
SELECTION = select_release(REPO, checkout=os.environ.get("HIMATE_DBOX_RELEASE_CHECKOUT"),
                           manifest_path=os.environ.get("HIMATE_DBOX_RELEASE_MANIFEST"))
RELEASE = SELECTION.root
MANUAL = load_manual(SELECTION, "dbox_portable_manual")


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def git(repository, *arguments):
    result = subprocess.run([
        "git", "-c", "core.hooksPath=" + os.devnull, "-c", "core.autocrlf=false",
        "-c", "core.longpaths=true",
        "-c", "commit.gpgsign=false", "-c", "user.name=Synthetic dbox fixture",
        "-c", "user.email=fixture@example.invalid", "-C", str(repository), *arguments,
    ], capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return result.stdout.decode().strip()


class PublicPipeline(MANUAL.ManualPipeline):
    """Keep every real CLI request/response and its elapsed wall time."""

    def call(self, slug, request, action=None, expected=0, *, environment=None):
        self.sequence += 1
        incoming = self.base / f"portable-in-{self.sequence}.json"
        outgoing = self.base / f"portable-out-{self.sequence}.json"
        incoming.write_bytes(canonical(request))
        if SELECTION.layout == "repository_cli":
            command = [sys.executable, "-X", "utf8", str(self.root / "knowledge.py"),
                       slug.removeprefix("hs-").removeprefix("knowledge-"), "--json",
                       "--input", str(incoming), "--output", str(outgoing),
                       "--knowledge-root", str(self.root)]
        else:
            command = [*SELECTION.command(self.root, slug, skills=self.skills),
                       "--input", str(incoming), "--output", str(outgoing),
                       "--knowledge-root", str(self.root)]
        if action:
            command += ["--action", action]
        started = time.perf_counter()
        process = subprocess.run(command, capture_output=True, timeout=180,
                                 env=environment)
        elapsed = time.perf_counter() - started
        result = json.loads(outgoing.read_bytes()) if outgoing.exists() else {}
        timings = self.base / "portable-cli-timings.jsonl"
        with timings.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"skill": slug, "action": action,
                "operation_id": request.get("operation_id"), "elapsed_seconds": elapsed,
                "returncode": process.returncode, "status": result.get("status"),
                "phase": result.get("phase")}) + "\n")
        assert process.returncode == expected, (result, process.stderr.decode(errors="replace"))
        return result


def document(kind):
    """Create known text and independent locator expectations for each adapter."""
    text = "Capture marker is a documented rule."
    if kind == "md":
        return ("# Source\n" + text + "\n").encode(), {"kind": "lines", "start": 1, "end": 2}
    if kind == "docx":
        import io
        from docx import Document
        item, stream = Document(), io.BytesIO()
        item.add_paragraph(text)
        item.save(stream)
        return stream.getvalue(), {"kind": "paragraph", "paragraph": 1}
    import io
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=100)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"):
        DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    content = DecodedStreamObject()
    content.set_data(("BT /F1 12 Tf 10 50 Td (" + text + ") Tj ET").encode())
    page[NameObject("/Contents")] = writer._add_object(content)
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue(), {"kind": "page", "page": 1}


def pending(base, kind="md"):
    pipeline = PublicPipeline(base)
    pipeline.catalog_path.unlink()
    (pipeline.root / ".isolated-knowledge-fixture").unlink()
    workspace = pipeline.root.parent
    configuration = {"schema_version": "2.0", "workspace_id": "portable-dbox",
        "knowledge_roots": {"wifi": pipeline.root.name}, "code_root": ".", "modules": []}
    (workspace / "config.yml").write_text(yaml.safe_dump(configuration), encoding="utf-8")
    from support.contracts import copy_workspace_metadata
    copy_workspace_metadata(workspace, pipeline.root, source_root=RELEASE,
                            source_knowledge_root=SELECTION.knowledge_root)
    for name in (".gitignore", "dbox.example.yml"):
        pipeline.write("docs-raw/sources/" + name,
            (SELECTION.knowledge_root / "docs-raw/sources" / name).read_bytes())
    git(workspace, "init", "-b", "main")
    runtime_assets = ([pipeline.root.name + "/" + name for name in
                       ("runtime", "knowledge.py", "knowledge.cmd", "knowledge.sh")]
                      if SELECTION.layout == "repository_cli" else [])
    git(workspace, "add", ".gitignore", ".gitattributes", "config.yml",
        pipeline.root.name + "/governance", *runtime_assets, pipeline.root.name + "/docs-raw/sources/.gitignore",
        pipeline.root.name + "/docs-raw/sources/dbox.example.yml")
    git(workspace, "commit", "-m", "Synthetic shared baseline")
    source = base / "生产者 外部目录" / "nested"
    source.mkdir(parents=True)
    original, locator = document(kind)
    relative = "nested/manual." + kind
    (source / ("manual." + kind)).write_bytes(original)
    external = source.parent
    configured = pipeline.call("knowledge-source", {"operation_id": "configure-producer",
        "path": str(external)}, "configure")
    assert configured["status"] == "ok", configured
    operation = "p"
    prepared = pipeline.call("knowledge-source", {"operation_id": operation}, "run")
    assert prepared["phase"] == "prepared", prepared
    scan_ref, material_ref = prepared["data"]["scan_ref"], prepared["data"]["material_ref"]
    bundle_ref = pipeline.record(material_ref)["bundle_ref"]
    bundle = pipeline.record(bundle_ref)
    assert len(bundle["resources"]) == 1 and len(bundle["snapshots"]) == 1
    card_id = "portable-dbox-rule"
    _, front, body = pipeline.card(card_id, bundle).decode().split("---", 2)
    metadata = yaml.safe_load(front)
    metadata["sources"][0]["locator"] = locator
    # This documents a synthetic implementation assertion, without code/build claims.
    # Both current and implementation must be usable before testing their refusal.
    metadata["claims"][0]["evidence_kind"] = "implementation"
    card = ("---\n" + yaml.safe_dump(metadata, sort_keys=False) + "---" + body).encode()
    view = pipeline.view(operation, bundle_ref, card_id, card,
        scan_ref=scan_ref, material_ref=material_ref,
        queries=[{"id": "portable-query", "query": "capture", "purpose": "current",
                  "required": [card_id], "expected_claim_ids": [card_id + "#c1"]}])
    pipeline.review(operation, view)
    request = {"operation_id": operation, "view_ref": view,
               "ingest_record_ref": pipeline.pending_record(operation, view)}
    return pipeline, external, relative, original, locator, metadata["sources"][0], bundle, request


def consumer_pipeline(base, root, skills):
    consumer = PublicPipeline.__new__(PublicPipeline)
    consumer.base, consumer.root, consumer.skills, consumer.sequence = base, root, skills, 0
    base.mkdir()
    return consumer


def search(pipeline, operation, purpose):
    return pipeline.call("knowledge-query", {"operation_id": operation,
        "query": "capture", "purpose": purpose}, "search")["data"]


def one_match(result):
    assert [row["card_id"] for row in result["matches"]] == ["portable-dbox-rule"], result
    return result["matches"][0]


def stop_before_activation(base):
    probe = base / "activation-stop-probe"
    probe.mkdir()
    marker = probe / "called.txt"
    script = '''from pathlib import Path
import sys
def profile(frame, event, value):
    if event == "call" and frame.f_code.co_name == "_activation_observation" and frame.f_code.co_filename.replace("\\\\", "/").endswith("/contracts/ingest_execution.py"):
        Path(MARKER).write_text("stopped after generation and regression", encoding="utf-8")
        sys.setprofile(None)
        raise RuntimeError("SYNTHETIC_PORTABLE_STOP_BEFORE_ACTIVATION")
sys.setprofile(profile)
'''.replace("MARKER", repr(str(marker)))
    (probe / "sitecustomize.py").write_text(script, encoding="utf-8")
    return {**os.environ, "PYTHONPATH": str(probe)}, marker
