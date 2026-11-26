#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""知识库上库：git add . + 固定模板 commit + git mm upload。

用法：
  python commit.py --repo <知识库仓根> --show-dts
  python commit.py --repo <知识库仓根> --description <中文摘要> --dts <DTS号> [--upload] [--dts-file <路径>]

固定提交模板（后两行不可改）：
  Description:<摘要>
  DTS:<DTS号>

  Team:WIFI
  Feature or Bugfix:Feature
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_DTS_REL = Path(".scratch") / "hs-knowledge-commit" / "dts.json"
CR_LINK_RE = re.compile(r"(https?://\S+?)\s+\[CR (?:CREATED|UPDATED)\]")
CR_FALLBACK_RE = re.compile(r"https?://\S*change_requests/\d+")

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    result = subprocess.run(cmd, cwd=str(cwd), capture_output=True)
    out = result.stdout.decode("utf-8", errors="replace")
    err = result.stderr.decode("utf-8", errors="replace")
    if out:
        print(out, end="")
    if err:
        print(err, end="", file=sys.stderr)
    return result.returncode, out + err


def dts_path(repo: Path, override: str | None) -> Path:
    return Path(override).expanduser() if override else repo / DEFAULT_DTS_REL


def load_dts(path: Path) -> str | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8")).get("dts")
    except (OSError, json.JSONDecodeError):
        return None
    return value.strip() if isinstance(value, str) and value.strip() else None


def save_dts(path: Path, dts: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"dts": dts}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def build_message(description: str, dts: str) -> str:
    return f"Description:{description}\nDTS:{dts}\n\nTeam:WIFI\nFeature or Bugfix:Feature"


def main() -> int:
    ap = argparse.ArgumentParser(description="知识库上库")
    ap.add_argument("--repo", required=True, help="知识库仓根绝对路径")
    ap.add_argument("--show-dts", action="store_true", help="打印上次使用的 DTS 单号")
    ap.add_argument("--description", help="中文提交摘要")
    ap.add_argument("--dts", help="DTS 单号，如 DTS2026103123684")
    ap.add_argument("--upload", action="store_true", help="提交后执行 git mm upload . -y")
    ap.add_argument(
        "--dts-file",
        help="DTS 记录文件路径，默认 <仓根>/.scratch/hs-knowledge-commit/dts.json",
    )
    args = ap.parse_args()

    repo = Path(args.repo).expanduser()
    if not repo.is_absolute():
        print(f"[拦截] --repo 须为绝对路径：{args.repo!r}", file=sys.stderr)
        return 2
    if not (repo / ".git").exists():
        print(f"[拦截] 不是 Git 仓根（缺少 .git）：{repo}", file=sys.stderr)
        return 2

    record = dts_path(repo, args.dts_file)

    if args.show_dts:
        dts = load_dts(record)
        if dts:
            print(dts)
            return 0
        print(f"[无记录] {record}", file=sys.stderr)
        return 1

    description = (args.description or "").strip()
    if not description:
        print("[拦截] 缺少 --description（中文摘要）", file=sys.stderr)
        return 2
    dts = (args.dts or "").strip() or load_dts(record)
    if not dts:
        print("[拦截] 缺少 DTS 单号：请向用户索取后传 --dts", file=sys.stderr)
        return 3

    code, _ = run(["git", "add", "."], repo)
    if code != 0:
        print("[失败] git add 未通过", file=sys.stderr)
        return code

    code, _ = run(["git", "commit", "-m", build_message(description, dts)], repo)
    if code != 0:
        print("[失败] git commit 未通过", file=sys.stderr)
        return code

    save_dts(record, dts)

    if not args.upload:
        return 0

    code, output = run(["git", "mm", "upload", ".", "-y"], repo)
    if code != 0:
        print("[失败] git mm upload 未通过", file=sys.stderr)
        return code

    match = CR_LINK_RE.search(output) or CR_FALLBACK_RE.search(output)
    if not match:
        print("[失败] 上传输出中未找到 [CR CREATED]/[CR UPDATED] 链接", file=sys.stderr)
        return 4
    link = match.group(1) if match.re is CR_LINK_RE else match.group(0)
    print(f"[CR] {link}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
