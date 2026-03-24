"""Conversation quality check — flag overly long sessions, suggest /compress."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from ..heal import Action, HealReport

LONG_SESSION_THRESHOLD = 100


def analyze_conversations(oc: Path, metrics: dict, report: HealReport, date: str) -> None:
    agents_dir = oc / "agents"
    if not agents_dir.exists():
        return

    long_sessions: list[str] = []
    inactive_agents: list[str] = []
    all_agents = [d.name for d in agents_dir.iterdir() if d.is_dir()]

    for agent in all_agents:
        sd = agents_dir / agent / "sessions"
        if not sd.exists():
            inactive_agents.append(agent)
            continue

        has_today = False
        for sf in sd.glob("*.jsonl"):
            try:
                mtime = datetime.fromtimestamp(sf.stat().st_mtime)
                if mtime.strftime("%Y-%m-%d") != date:
                    continue
            except OSError:
                continue

            has_today = True
            msg_count = 0
            try:
                with open(sf, encoding="utf-8") as f:
                    for line in f:
                        try:
                            d = json.loads(line)
                            if d.get("type") == "message":
                                msg_count += 1
                        except json.JSONDecodeError:
                            continue
            except OSError:
                continue

            if msg_count > LONG_SESSION_THRESHOLD:
                long_sessions.append(f"{agent}/{sf.stem[:8]}... ({msg_count} msgs)")

        if not has_today and agent not in inactive_agents:
            inactive_agents.append(agent)

    issues = []
    if long_sessions:
        issues.append(f"过长 session (>{LONG_SESSION_THRESHOLD} msgs): " + ", ".join(long_sessions[:3]))
        report.suggestions.append(f"{len(long_sessions)} 个 session 对话过长，建议执行 /compress 压缩")
    if len(inactive_agents) >= 3:
        report.suggestions.append(f"{len(inactive_agents)} 个 Agent 今日无活动: {', '.join(inactive_agents[:4])}")

    if not issues:
        return

    action = Action(
        id="conversation_quality", category="conversation", level="safe",
        title=f"对话质量: {len(long_sessions)} 个过长 session",
        detail="\n".join(issues),
        executed=True,
        result=f"已标记 {len(long_sessions)} 个需要压缩的 session",
    )
    report.add(action)
