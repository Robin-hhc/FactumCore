"""Synthetic card bytes shared by contract scenarios."""
import yaml

def card_data(**overrides):
    meta = dict(
        schema_version="2.0",
        id="card-a",
        profile="entity",
        title="对象",
        summary="职责摘要",
        lifecycle="draft",
        review_mode="manual_document",
        owner="author",
        aliases=[],
        scope={"applicability": "unknown", "contexts": []},
        sources=[
            {
                "evidence_ref": "e1",
                "source_id": "s1",
                "snapshot_id": "raw:one",
                "locator": {"kind": "lines", "start": 1, "end": 1},
            }
        ],
        claims=[
            dict(
                id="c1",
                text_ref="#c1",
                evidence_kind="design",
                source_refs=["e1"],
                context_ids=[],
                usage="guidance",
                verification_requirements=[],
            )
        ],
        relations=[],
    )
    meta.update(overrides)
    body = '# 对象\n<a id="c1"></a>\n职责说明。\n\n' + "\n".join(
        "## " + x + "\n说明\n" for x in ("职责", "边界", "接口", "依赖", "证据")
    )
    return ("---\n" + yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) + "---\n" + body).encode("utf-8")
