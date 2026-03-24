"""Memory optimization — scan for truly duplicate content, stale entries."""
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
    stale: list[str] = []
    content_hashes: dict[str, list[str]] = defaultdict(list)
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
                content = f.read_text(encoding="utf-8").strip()
                if len(content) < 20:
                    try:
                        mtime = datetime.fromtimestamp(f.stat().st_mtime)
                        if mtime < cutoff:
                            stale.append(str(f.relative_to(oc)))
                    except OSError:
                        pass
                    continue

                h = hashlib.sha256(content.encode()).hexdigest()
                rel = str(f.relative_to(oc))
                content_hashes[h].append(rel)
            except (OSError, UnicodeDecodeError):
                continue

    MIRROR_PAIRS = {"xiaoxia-memory-repo", "workspace"}

    true_duplicates: list[dict] = []
    for h, paths in content_hashes.items():
        if len(paths) <= 1:
            continue
        # Filter out cross-directory mirrors (same file in repo + workspace)
        basenames = set()
        unique_paths = []
        for p in paths:
            bn = p.split("\\")[-1].split("/")[-1]
            if bn not in basenames:
                basenames.add(bn)
                unique_paths.append(p)

        dirs = {p.split("\\")[0].split("/")[0] for p in paths}
        is_mirror = len(unique_paths) <= 1 and len(dirs & MIRROR_PAIRS) >= 2
        if is_mirror:
            continue

        if len(unique_paths) > 1:
            true_duplicates.append({
                "count": len(unique_paths),
                "files": unique_paths[:3],
                "preview": unique_paths[0][:60],
            })

    issues = []
    if true_duplicates:
        issues.append(f"{len(true_duplicates)} 组内容完全相同的记忆文件")
        dup_details = []
        for d in sorted(true_duplicates, key=lambda x: x["count"], reverse=True)[:5]:
            dup_details.append(f"  {d['count']} 份: {d['files'][0]}")
        report.suggestions.append(
            f"发现 {len(true_duplicates)} 组内容完全重复的记忆文件（sha256 相同），建议去重:\n" +
            "\n".join(dup_details)
        )
    if stale:
        issues.append(f"{len(stale)} 个过小且过旧的记忆 (>14天, <20字符)")

    detail = "\n".join(issues) if issues else f"记忆库健康: {total_files} 个文件, 无真正重复"

    action = Action(
        id="memory_optimize", category="memory",
        level="risky" if true_duplicates else "safe",
        title=f"记忆分析: {total_files} 个文件 ({total_bytes // 1024}KB), {len(true_duplicates)} 组真正重复",
        detail=detail,
        executed=not bool(true_duplicates),
        result=f"{len(true_duplicates)} 组内容重复, {len(stale)} 个可能过期" if issues else "无异常",
    )
    report.add(action)
