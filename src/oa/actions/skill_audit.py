"""Skill health audit — find missing SKILL.md, stale skills."""
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
from ..heal import Action, HealReport

STALE_DAYS = 30


def check_skills(oc: Path, report: HealReport, dry_run: bool) -> None:
    skills_dir = oc / "workspace" / "skills"
    if not skills_dir.exists():
        return

    missing_skill_md = []
    stale_skills = []
    total = 0
    cutoff = datetime.now() - timedelta(days=STALE_DAYS)

    for sd in skills_dir.iterdir():
        if not sd.is_dir():
            continue
        total += 1
        if not (sd / "SKILL.md").exists():
            missing_skill_md.append(sd.name)
        try:
            mtime = datetime.fromtimestamp(sd.stat().st_mtime)
            if mtime < cutoff:
                stale_skills.append(sd.name)
        except OSError:
            pass

    issues = []
    if missing_skill_md:
        issues.append(f"缺少 SKILL.md: {', '.join(missing_skill_md)}")
    if stale_skills:
        issues.append(f"{len(stale_skills)} 个技能超过 {STALE_DAYS} 天未更新")

    if not issues:
        return

    has_issues = bool(missing_skill_md) or bool(stale_skills)
    action = Action(
        id="skill_audit", category="skill", level="safe",
        title=f"技能巡检: {total} 个技能, {len(issues)} 个问题",
        detail="\n".join(issues),
        metric="queue_throughput",
        executed=not has_issues,
        result=f"缺少 SKILL.md: {missing_skill_md}" if missing_skill_md else "全部正常",
    )
    report.add(action)
