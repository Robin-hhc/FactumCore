"""Shared public-pipeline fixture; no test cases."""
import json
import subprocess
from support import pipeline as FIXTURE

class ManualPipeline(FIXTURE.Pipeline):
    def call(self, slug, request, action=None, expected=0):
        slug, request, action = FIXTURE.target_call(slug, request, action)
        self.sequence += 1
        incoming = self.base / f"manual-in-{self.sequence}.json"
        outgoing = self.base / f"manual-out-{self.sequence}.json"
        # Harness metadata is irrelevant to the business CLI, even if malformed.
        incoming.write_bytes(FIXTURE.canonical({**request, "workflow": "host-owned"}))
        command = [
            *self.command(slug),
            "--input", str(incoming), "--output", str(outgoing),
            "--knowledge-root", str(self.root),
        ]
        if action:
            command += ["--action", action]
        process = subprocess.run(command, capture_output=True, timeout=180)
        response = json.loads(outgoing.read_bytes())
        assert process.returncode == expected, (response, process.stderr.decode(errors="replace"))
        assert "artifact_manifest_ref" not in response.get("data", {})
        return response
