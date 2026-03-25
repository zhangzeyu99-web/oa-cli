"""OA Self-Improvement Engine — diagnose anomalies, plan actions, execute or notify."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Action:
    id: str
    category: str
    level: str  # "safe", "risky", "blocked"
    title: str
    detail: str
    metric: str = ""
    executed: bool = False
    result: str = ""
    bytes_freed: int = 0


@dataclass
class HealReport:
    date: str
    actions: list[Action] = field(default_factory=list)
    safe_executed: int = 0
    risky_notified: int = 0
    suggestions: list[str] = field(default_factory=list)

    def add(self, action: Action):
        self.actions.append(action)

    def summary_text(self) -> str:
        lines = [
            f"OA 自动改进报告 | {self.date}",
            "=" * 40,
        ]

        executed = [a for a in self.actions if a.executed]
        risky = [a for a in self.actions if a.level == "risky" and not a.executed]
        suggestions = [a for a in self.actions if a.level == "safe" and not a.executed]

        if executed:
            lines.append(f"\n[已自动修复] {len(executed)} 项")
            for a in executed:
                freed = f" (回收 {a.bytes_freed // 1024 // 1024}MB)" if a.bytes_freed > 0 else ""
                lines.append(f"  {a.title}{freed}")
                if a.result:
                    lines.append(f"    -> {a.result}")

        if risky:
            lines.append(f"\n[需要你确认] {len(risky)} 项")
            for a in risky:
                lines.append(f"  {a.title}")
                lines.append(f"    {a.detail}")

        if suggestions or self.suggestions:
            lines.append(f"\n[改进建议]")
            for a in suggestions:
                lines.append(f"  {a.title}: {a.detail}")
            for s in self.suggestions:
                lines.append(f"  {s}")

        total_freed = sum(a.bytes_freed for a in executed)
        if total_freed > 0:
            lines.append(f"\n[存储回收] {total_freed // 1024 // 1024}MB")

        # 处理分类明细表
        lines.append(f"\n{'─' * 40}")
        lines.append("[处理分类明细]")
        lines.append(f"{'─' * 40}")

        CATEGORY_NAMES = {
            "session": "Session 管理",
            "cron": "Cron 自愈",
            "skill": "技能巡检",
            "knowledge": "知识整理",
            "path": "路径监控",
            "cost": "模型成本",
            "conversation": "对话质量",
            "memory": "记忆优化",
            "gateway": "Gateway 守护",
        }

        for a in self.actions:
            cat = CATEGORY_NAMES.get(a.category, a.category)
            if a.executed:
                level_tag = "自动"
            elif a.level == "risky":
                level_tag = "需确认"
            elif a.level == "blocked":
                level_tag = "禁止"
            else:
                level_tag = "建议"

            status = "已处理" if a.executed else ("待确认" if a.level == "risky" else "仅建议")
            lines.append(f"  [{level_tag}] {cat}: {status}")
            short_detail = a.detail.split("\n")[0][:60] if a.detail else ""
            if short_detail:
                lines.append(f"         {short_detail}")

        lines.append(f"\n{'=' * 40}")
        lines.append(f"时间: {datetime.now().strftime('%H:%M:%S')}")
        lines.append("Dashboard: http://localhost:3460")
        return "\n".join(lines)


def load_metrics(db_path: Path, date: str) -> dict[str, dict[str, float]]:
    """Load today's metrics grouped by goal."""
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row
    rows = db.execute(
        "SELECT goal, metric, value, unit FROM goal_metrics WHERE date=?", (date,)
    ).fetchall()
    db.close()
    result: dict[str, dict[str, float]] = {}
    for r in rows:
        if r["goal"] not in result:
            result[r["goal"]] = {}
        result[r["goal"]][r["metric"]] = r["value"]
    return result


def load_thresholds(config_path: Path) -> dict[str, dict[str, dict[str, float]]]:
    """Load healthy/warning thresholds from config.yaml."""
    with open(config_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    result: dict[str, dict[str, dict[str, float]]] = {}
    for g in cfg.get("goals", []):
        gid = g["id"]
        result[gid] = {}
        for m in g.get("metrics", []):
            result[gid][m["name"]] = {"healthy": m.get("healthy", 0), "warning": m.get("warning", 0)}
    return result


def diagnose(metrics: dict, thresholds: dict) -> list[dict]:
    """Compare metrics against thresholds, return anomalies.

    Supports both "higher is better" (healthy > warning, e.g. success_rate)
    and "lower is better" (healthy < warning, e.g. memory_duplicates).
    """
    anomalies = []
    for goal, goal_metrics in metrics.items():
        gt = thresholds.get(goal, {})
        for metric, value in goal_metrics.items():
            mt = gt.get(metric, {})
            healthy = mt.get("healthy", 0)
            warning = mt.get("warning", 0)

            if healthy >= warning:
                # Higher is better (e.g. success_rate: healthy=95, warning=80)
                if value < warning:
                    severity = "critical"
                elif value < healthy:
                    severity = "warning"
                else:
                    continue
            else:
                # Lower is better (e.g. duplicates: healthy=10, warning=50)
                if value > warning:
                    severity = "critical"
                elif value > healthy:
                    severity = "warning"
                else:
                    continue

            anomalies.append({"goal": goal, "metric": metric, "value": value,
                              "healthy": healthy, "warning": warning, "severity": severity})
    return anomalies


def run_heal(config_path: str, dry_run: bool = False, safe_only: bool = False) -> HealReport:
    """Main heal entry point."""
    from .actions.session_cleanup import check_session_bloat
    from .actions.cron_heal import check_cron_health
    from .actions.skill_audit import check_skills
    from .actions.knowledge_tidy import check_knowledge
    from .actions.path_monitor import check_paths
    from .actions.gateway_guard import check_gateway
    from .actions.cost_analysis import analyze_cost
    from .actions.conversation_quality_check import analyze_conversations
    from .actions.memory_optimize import analyze_memory

    cfg_path = Path(config_path)
    with open(cfg_path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    db_path_raw = cfg.get("db_path", "data/monitor.db")
    db_path = Path(db_path_raw) if Path(db_path_raw).is_absolute() else (cfg_path.parent / db_path_raw)
    oc_home = Path(cfg.get("openclaw_home", str(Path.home() / ".openclaw")))
    date = datetime.now().strftime("%Y-%m-%d")

    metrics = load_metrics(db_path, date)
    thresholds = load_thresholds(cfg_path)
    anomalies = diagnose(metrics, thresholds)

    report = HealReport(date=date)

    # SAFE actions — always run
    check_session_bloat(oc_home, report, dry_run)
    check_cron_health(oc_home, report, dry_run)
    check_skills(oc_home, report, dry_run)
    check_knowledge(oc_home, report, dry_run)
    check_paths(oc_home, report, dry_run)
    analyze_cost(oc_home, report, date)
    analyze_conversations(oc_home, metrics, report, date)
    analyze_memory(oc_home, report)

    # RISKY actions — only if not safe_only
    if not safe_only:
        check_gateway(oc_home, metrics, report, dry_run)

    report.safe_executed = sum(1 for a in report.actions if a.executed)
    report.risky_notified = sum(1 for a in report.actions if a.level == "risky" and not a.executed)

    # Write heal diagnostics to DB for Dashboard
    _write_heal_metrics(db_path, date, report, oc_home)

    return report


def _write_heal_metrics(db_path: Path, date: str, report: HealReport, oc_home: Path) -> None:
    """Write heal diagnostic results into goal_metrics for Dashboard display, with tracing."""
    import sqlite3
    from .core.tracing import Tracer

    tracer = Tracer(service="self_improvement", db_path=db_path)
    db = sqlite3.connect(str(db_path))
    db.execute("PRAGMA journal_mode=WAL")

    DATA_FLOW = [
        {"from": "heal actions", "to": "extract_metrics.py", "type": "data"},
        {"from": "cron/runs/*.jsonl", "to": "cost_analysis.py", "type": "data"},
        {"from": "agents/*/sessions", "to": "conversation_check.py", "type": "data"},
        {"from": "workspace/skills", "to": "skill_audit.py", "type": "data"},
        {"from": "memory/*.md", "to": "memory_optimize.py", "type": "data"},
        {"from": "extract_metrics.py", "to": "goal_metrics", "type": "write"},
    ]
    NODE_TYPES = {
        "heal actions": "script",
        "cron/runs/*.jsonl": "source",
        "agents/*/sessions": "agent",
        "workspace/skills": "source",
        "memory/*.md": "source",
        "extract_metrics.py": "script",
        "cost_analysis.py": "script",
        "conversation_check.py": "script",
        "skill_audit.py": "script",
        "memory_optimize.py": "script",
        "goal_metrics": "db",
    }

    with tracer.span("Self Improvement", {
        "date": date,
        "data_flow_edges": DATA_FLOW,
        "node_types": NODE_TYPES,
    }) as root:

        def upsert(goal: str, metric: str, value: float, unit: str = "count") -> None:
            db.execute(
                """INSERT INTO goal_metrics (date, goal, metric, value, unit)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(date, goal, metric) DO UPDATE SET value=excluded.value""",
                (date, goal, metric, value, unit),
            )

        import re as _re

        with tracer.span("Extract Token Cost", {"step": "compute"}) as s1:
            cost_action = next((a for a in report.actions if a.id == "cost_analysis"), None)
            total_tokens = 0
            model_breakdown = {}
            if cost_action and cost_action.result:
                try:
                    cost_data = json.loads(cost_action.result)
                    total_tokens = cost_data.get("total", 0)
                    model_breakdown = cost_data.get("models", {})
                except (json.JSONDecodeError, TypeError):
                    m = _re.search(r"(\d[\d,]*)\s*tokens", cost_action.title)
                    total_tokens = int(m.group(1).replace(",", "")) if m else 0
            breakdown_json = json.dumps(model_breakdown, ensure_ascii=False) if model_breakdown else None
            db.execute(
                """INSERT INTO goal_metrics (date, goal, metric, value, unit, breakdown)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(date, goal, metric) DO UPDATE SET value=excluded.value, breakdown=excluded.breakdown""",
                (date, "self_improvement", "daily_tokens", total_tokens, "count", breakdown_json),
            )
            s1.set_attribute("total_tokens", total_tokens)
            s1.set_attribute("models", list(model_breakdown.keys()))

        with tracer.span("Extract Memory Duplicates", {"step": "compute"}) as s2:
            mem_action = next((a for a in report.actions if a.id == "memory_optimize"), None)
            dup_count = 0
            if mem_action:
                m = _re.search(r"(\d+)\s*组", mem_action.detail)
                dup_count = int(m.group(1)) if m else 0
            upsert("self_improvement", "memory_duplicates", dup_count)
            s2.set_attribute("duplicates", dup_count)

        with tracer.span("Extract Long Sessions", {"step": "compute"}) as s3:
            conv_action = next((a for a in report.actions if a.id == "conversation_quality"), None)
            long_count = 0
            if conv_action:
                m = _re.search(r"(\d+)\s*个过长", conv_action.title)
                long_count = int(m.group(1)) if m else 0
            upsert("self_improvement", "long_sessions", long_count)
            s3.set_attribute("long_sessions", long_count)

        with tracer.span("Extract Skill Health", {"step": "compute"}) as s4:
            skill_action = next((a for a in report.actions if a.id == "skill_audit"), None)
            missing = 0
            if skill_action and skill_action.result:
                names = _re.findall(r"'([\w\-]+)'", skill_action.result)
                missing = len(names)
            upsert("self_improvement", "skills_missing_doc", missing)
            s4.set_attribute("missing_skills", missing)

        with tracer.span("Compute Heal Score", {"step": "compute"}) as s5:
            total_actions = len(report.actions)
            heal_score = round(report.safe_executed / total_actions * 100, 1) if total_actions else 100
            upsert("self_improvement", "heal_score", heal_score, "%")
            s5.set_attribute("score", heal_score)
            s5.set_attribute("executed", report.safe_executed)
            s5.set_attribute("total", total_actions)

        root.set_attribute("tokens", total_tokens)
        root.set_attribute("duplicates", dup_count)
        root.set_attribute("long_sessions", long_count)
        root.set_attribute("heal_score", heal_score)

    db.commit()
    db.close()
    tracer.flush()
