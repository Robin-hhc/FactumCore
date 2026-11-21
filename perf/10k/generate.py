"""Create and verify the fixed FactumCore 10,000-card performance fixture."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from pathlib import PurePosixPath
import posixpath


DOCUMENTS = 1000
CARDS_PER_DOCUMENT = 10
KNOWLEDGE = PurePosixPath("himate/himate-knowledge-wifi-mp")
CODE_ROOT = PurePosixPath("main/perf-10k")
SPEC_DIR = PurePosixPath("perf/10k")
MANIFEST = SPEC_DIR / "fixture.json"
RAW_DIRECTORY = PurePosixPath("docs-raw/specs/perf-10k")
CARD_DIRECTORIES = (
    "concepts/entities", "concepts/flows", "concepts/protocols",
    "rules", "commands", "runbooks", "glossaries",
)
AREAS = (
    ("rx-queue", "接收队列"),
    ("tx-budget", "发送预算"),
    ("retry", "重试计数"),
    ("buffer", "缓冲容量"),
    ("session", "会话配额"),
    ("scheduler", "调度批次"),
    ("telemetry", "遥测采样"),
    ("link", "链路状态"),
    ("power", "省电轮询"),
    ("recovery", "故障恢复"),
)
PROCESSED_AT = "2000-01-01T00:00:00+00:00"


def card_path(number, area):
    category = CARD_DIRECTORIES[(number - 1) % len(CARD_DIRECTORIES)]
    return PurePosixPath("knowledge") / category / "perf-10k" / area / f"perf-card-{number:05d}.md"


def source_entry(source_id, kind, path, data):
    entry = {"source_id": source_id, "kind": kind, "path": path.as_posix()}
    if kind == "code":
        entry["encoding"] = "utf-8"
    entry.update(processed_hash=sha256(data).hexdigest(), processed_exists=True,
                 processed_at=PROCESSED_AT, source_commit=None)
    return entry


def generate(documents=DOCUMENTS):
    files = {}
    resources = []
    for doc_number in range(1, documents + 1):
        area, area_title = AREAS[(doc_number - 1) % len(AREAS)]
        doc_id = f"perf-doc-{doc_number:04d}"
        raw_path = RAW_DIRECTORY / area / f"{doc_id}.md"
        raw_lines = [
            f"# {area_title}合成规格 {doc_id}",
            "",
            "本文件为 FactumCore 查询和索引性能测试生成。计数、阈值和行为均为合成样例。",
            "",
        ]
        first = (doc_number - 1) * CARDS_PER_DOCUMENT + 1
        for ordinal in range(CARDS_PER_DOCUMENT):
            number = first + ordinal
            case = f"{number:05d}"
            card_id = f"perf-card-{case}"
            code_id = f"perf-code-{case}"
            symbol = f"perf_clamp_{case}"
            limit = 8 + (number * 17 % 249)
            raw_start = len(raw_lines) + 1
            raw_lines.extend([
                f"## 用例 {case} 的无线队列限制",
                "",
                f"本用例用 {symbol} 归一化 {area_title}请求中的计数，阈值为 {limit}。",
                f"输入不超过 {limit} 时保留计数。较大的输入返回 {limit}，以维持队列预算。",
                "测试覆盖零值、阈值和阈值加一。观察值按同一用例号归档，便于对比原件、知识卡与实现。",
                "",
            ])
            raw_end = len(raw_lines) - 1
            code_path = CODE_ROOT / area / f"{symbol}.c"
            code = ("/* Synthetic FactumCore performance fixture. */\n\n"
                    f"unsigned int {symbol}(unsigned int count)\n"
                    "{\n"
                    f"    const unsigned int limit = {limit}u;\n"
                    "    return count > limit ? limit : count;\n"
                    "}\n").encode("utf-8")
            files[code_path] = code
            resources.append(source_entry(code_id, "code", code_path, code))

            relative = card_path(number, area)
            linked = card_path(first + (ordinal + 1) % CARDS_PER_DOCUMENT, area)
            link = posixpath.relpath(linked.as_posix(), relative.parent.as_posix())
            metadata = [
                "---",
                f"id: {card_id}",
                "doc_ref:",
                f"- doc_id: {doc_id}",
                f"  line_start: {raw_start}",
                f"  line_end: {raw_end}",
                "code_ref:",
                f"- code_id: {code_id}",
                f"  symbol: {symbol}",
                "  line_start: 3",
                f"  line_end: {len(code.splitlines())}",
                f"tags: [perf-10k, radio, {area}]",
                "lifecycle: stable",
                "---",
            ]
            body = [
                f"# {area_title}阈值用例 {case}",
                "",
                f"用例 case{case} 记录 {area_title}中无线队列计数的边界行为。",
                "",
                "## 适用条件",
                "",
                f"合成请求进入归一化阶段。参数为无符号计数，所属测试组为 {area}。",
                "",
                "## 行为与验证",
                "",
                f"实现函数为 `{symbol}`。零值保持为零，阈值 {limit} 保持原值，"
                f"输入 {limit + 1} 时返回 {limit}。",
                "本规则用于固定输入分布和校验命中范围。查看原件段落可核对条件，"
                "定位到代码定义可确认上界和返回值。",
                "",
                f"[同原件下一用例]({link})",
            ]
            files[KNOWLEDGE / relative] = ("\n".join(metadata + body) + "\n").encode("utf-8")
        raw = ("\n".join(raw_lines[:-1]) + "\n").encode("utf-8")
        files[KNOWLEDGE / raw_path] = raw
        resources.append(source_entry(doc_id, "raw", raw_path, raw))

    rows = sorted(resources, key=lambda entry: entry["source_id"])
    ledger = "\n".join(["schema_version: '2.0'", "resources:"] +
                       ["- " + json.dumps(row, ensure_ascii=False) for row in rows] +
                       ["snapshots: []", ""])
    files[KNOWLEDGE / "governance/sources.lock.yaml"] = ledger.encode("utf-8")
    files[KNOWLEDGE / "config.yml"] = (
        "# Synthetic performance fixture.\n"
        "schema_version: '2.0'\nworkspace_id: perf-wifi-10k-v1\n"
        "code_root: ../../main\nmodules:\n- path: perf-10k\n"
        "query:\n  default_channel: local\n  allowed_channels: [local, shared]\n"
    ).encode("utf-8")

    digest = sha256()
    for relative, data in sorted(files.items()):
        digest.update(f"{relative.as_posix()}\n{sha256(data).hexdigest()}\n".encode("ascii"))
    card_count = documents * CARDS_PER_DOCUMENT
    manifest = {
        "fixture": "perf-10k-v1",
        "raw_documents": documents,
        "knowledge_cards": card_count,
        "code_sources": card_count,
        "doc_refs": card_count,
        "code_refs": card_count,
        "card_links": card_count,
        "payload_bytes": sum(map(len, files.values())),
        "content_sha256": digest.hexdigest(),
    }
    files[MANIFEST] = (json.dumps(manifest, indent=2) + "\n").encode("utf-8")
    return files


def write_files(root, files):
    root.mkdir(parents=True, exist_ok=False)
    for relative, data in files.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def verify(root, files):
    fixture_dirs = [KNOWLEDGE / RAW_DIRECTORY, CODE_ROOT]
    fixture_dirs.extend(KNOWLEDGE / category / "perf-10k" for category in CARD_DIRECTORIES)
    for directory in fixture_dirs:
        extra = next((path for path in (root / directory).rglob("*")
                      if path.is_file() and PurePosixPath(path.relative_to(root).as_posix()) not in files), None)
        if extra is not None:
            raise SystemExit(f"Unexpected fixture file: {extra.relative_to(root)}")
    for relative, expected in files.items():
        target = root / relative
        if not target.is_file() or target.read_bytes() != expected:
            raise SystemExit(f"Missing or changed fixture file: {relative}")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("mode", choices=("create", "verify"))
    cli.add_argument("root", type=Path)
    args = cli.parse_args()
    files = generate()
    if args.mode == "create":
        write_files(args.root, files)
    else:
        verify(args.root, files)
    print(files[MANIFEST].decode("utf-8"), end="")


if __name__ == "__main__":
    main()
