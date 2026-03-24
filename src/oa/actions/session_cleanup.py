"""Session bloat management — clean archived .reset/.deleted/.bak files older than 7 days."""
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
from ..heal import Action, HealReport

ARCHIVE_SUFFIXES = (".reset.", ".deleted.", ".bak")
MAX_AGE_DAYS = 7


def check_session_bloat(oc: Path, report: HealReport, dry_run: bool) -> None:
    agents_dir = oc / "agents"
    if not agents_dir.exists():
        return

    cutoff = datetime.now() - timedelta(days=MAX_AGE_DAYS)
    stale_files: list[tuple[Path, int]] = []
    total_archived = 0
    total_archived_bytes = 0

    for ad in agents_dir.iterdir():
        if not ad.is_dir():
            continue
        sd = ad / "sessions"
        if not sd.exists():
            continue
        for f in sd.iterdir():
            if not f.is_file():
                continue
            is_archive = any(s in f.name for s in ARCHIVE_SUFFIXES)
            if not is_archive:
                continue
            total_archived += 1
            sz = f.stat().st_size
            total_archived_bytes += sz
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime < cutoff:
                    stale_files.append((f, sz))
            except OSError:
                continue

    if not stale_files:
        return

    stale_bytes = sum(s for _, s in stale_files)

    if dry_run:
        action = Action(
            id="session_cleanup", category="session", level="safe",
            title=f"Session 归档清理: {len(stale_files)} 个文件 ({stale_bytes // 1024 // 1024}MB)",
            detail=f"共 {total_archived} 个归档文件 ({total_archived_bytes // 1024 // 1024}MB), 其中 {len(stale_files)} 个超过 {MAX_AGE_DAYS} 天",
            metric="session_storage_mb",
            bytes_freed=stale_bytes,
        )
        report.add(action)
        return

    deleted = 0
    freed = 0
    for f, sz in stale_files:
        try:
            f.unlink()
            deleted += 1
            freed += sz
        except OSError:
            continue

    action = Action(
        id="session_cleanup", category="session", level="safe",
        title=f"Session 归档清理: 删除 {deleted} 个过期文件",
        detail=f"回收 {freed // 1024 // 1024}MB (共 {total_archived} 个归档文件)",
        metric="session_storage_mb",
        executed=True,
        result=f"删除 {deleted}/{len(stale_files)} 个文件, 回收 {freed // 1024 // 1024}MB",
        bytes_freed=freed,
    )
    report.add(action)
