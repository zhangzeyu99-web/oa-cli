"""Memory optimization — scan for duplicates, stale entries, growth analysis."""
from __future__ import annotations
import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from ..heal import Action, HealReport


def analyze_memory(oc: Path, report: HealReport) -> None:
    mem_dirs = [oc / "xiaoxia-memory-repo", oc / "workspace" / "memory"]
    total_files = 0
    total_bytes = 0
    duplicates: list[str] = []
    stale: list[str] = []
    hashes: dict[str, list[str]] = defaultdict(list)
    cutoff = datetime.now() - timedelta(days=14)

    for md in mem_dirs:
        if not md.exists():
            continue
        for f in md.rglob("*.md"):
            if f.name.startswith("."):
                continue
            total_files += 1
            sz = f.stat().st_size
            total_bytes += sz

            try:
                content = f.read_bytes()[:2000]
                h = hashlib.md5(content).hexdigest()
                hashes[h].append(str(f.relative_to(oc)))
            except OSError:
                continue

            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime < cutoff and sz < 200:
                    stale.append(str(f.relative_to(oc)))
            except OSError:
                continue

    for h, paths in hashes.items():
        if len(paths) > 1:
            duplicates.append(f"可能重复 ({len(paths)} 份): {paths[0][:50]}")

    issues = []
    if duplicates:
        issues.append(f"{len(duplicates)} 组可能重复的记忆文件")
        report.suggestions.append(f"发现 {len(duplicates)} 组可能重复的记忆文件，建议人工审查后去重")
    if stale:
        issues.append(f"{len(stale)} 个小且过旧的记忆文件 (>14天, <200字节)")

    action = Action(
        id="memory_optimize", category="memory", level="risky" if duplicates else "safe",
        title=f"记忆分析: {total_files} 个文件 ({total_bytes // 1024}KB)",
        detail="\n".join(issues) if issues else f"记忆库健康: {total_files} 个文件, 无明显问题",
        executed=not bool(duplicates),
        result=f"分析完成, {len(duplicates)} 组重复, {len(stale)} 个可能过期" if issues else "无异常",
    )
    report.add(action)
