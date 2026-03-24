"""Cron self-healing — detect failed OA cron jobs and fix PATH/timeout issues."""
from __future__ import annotations
import json
from pathlib import Path
from ..heal import Action, HealReport


def check_cron_health(oc: Path, report: HealReport, dry_run: bool) -> None:
    jobs_file = oc / "cron" / "jobs.json"
    if not jobs_file.exists():
        return

    try:
        data = json.loads(jobs_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        report.add(Action(
            id="cron_heal", category="cron", level="risky",
            title="Cron jobs.json 解析失败",
            detail=f"文件可能损坏: {jobs_file}",
        ))
        return
    issues = []

    for job in data.get("jobs", []):
        if not job.get("enabled", True):
            continue
        jid = job.get("id", "")
        name = job.get("name", jid)
        state = job.get("state", {})
        errors = state.get("consecutiveErrors", 0)
        last_status = state.get("lastStatus", state.get("lastRunStatus", "unknown"))

        if errors > 0:
            issues.append(f"{name}: {errors} 连续错误 (last={last_status})")

        if "oa" in jid.lower() or "oa" in name.lower():
            payload_msg = job.get("payload", {}).get("message", "")
            if "oa-collect.cmd" not in payload_msg and "oa collect" in payload_msg.lower():
                issues.append(f"{name}: payload 未使用包装脚本路径")

    if not issues:
        return

    action = Action(
        id="cron_heal", category="cron", level="safe",
        title=f"Cron 健康检查: {len(issues)} 个问题",
        detail="\n".join(issues),
        metric="success_rate",
    )
    report.add(action)
