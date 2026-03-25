"""Knowledge tidy — clean expired AutoSkill sessions, flag duplicates."""
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
from ..heal import Action, HealReport

MAX_EMBEDDED_SESSIONS = 80
KEEP_SESSIONS = 60


def check_knowledge(oc: Path, report: HealReport, dry_run: bool) -> None:
    as_dir = oc / "autoskill" / "embedded_sessions"
    if not as_dir.exists():
        return

    try:
        sessions = sorted(
            [d for d in as_dir.iterdir() if d.is_dir()],
            key=lambda d: d.stat().st_mtime,
        )
    except OSError:
        return
    total = len(sessions)

    if total <= MAX_EMBEDDED_SESSIONS:
        return

    to_remove = sessions[: total - KEEP_SESSIONS]
    remove_bytes = sum(
        sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
        for d in to_remove
    )

    if dry_run:
        action = Action(
            id="knowledge_tidy", category="knowledge", level="safe",
            title=f"AutoSkill 清理: {len(to_remove)} 个过期 session",
            detail=f"总计 {total} 个 embedded sessions, 保留最近 {KEEP_SESSIONS} 个, 清理 {len(to_remove)} 个 ({remove_bytes // 1024}KB)",
            metric="vectordb_documents",
            bytes_freed=remove_bytes,
        )
        report.add(action)
        return

    deleted = 0
    freed = 0
    import shutil
    for d in to_remove:
        try:
            sz = sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
            shutil.rmtree(d)
            deleted += 1
            freed += sz
        except OSError:
            continue

    action = Action(
        id="knowledge_tidy", category="knowledge", level="safe",
        title=f"AutoSkill 清理: 删除 {deleted} 个过期 session",
        detail=f"保留最近 {KEEP_SESSIONS} 个",
        metric="vectordb_documents",
        executed=True,
        result=f"删除 {deleted} sessions, 回收 {freed // 1024}KB",
        bytes_freed=freed,
    )
    report.add(action)
