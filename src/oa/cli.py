"""OA CLI — the main entry point."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from . import __version__

console = Console()


@click.group()
@click.version_option(__version__, prog_name="oa")
def main():
    """OA — Operational Analytics for your AI agent team."""
    pass


# ━━━ oa init ━━━

@main.command()
@click.argument("name", default="oa-project")
@click.option("--yes", "-y", is_flag=True, help="Accept defaults, skip prompts")
def init(name: str, yes: bool):
    """Auto-detect OpenClaw setup and create an OA project."""
    from .core.scanner import OpenClawScanner
    from .core.config import ProjectConfig
    from .core.schema import create_schema

    project = Path(name)
    if project.exists():
        console.print(f"[red]Error:[/] Directory '{name}' already exists.")
        raise SystemExit(1)

    # Scan OpenClaw
    console.print("\n[bright_magenta]🔍 Scanning OpenClaw installation...[/]\n")
    scanner = OpenClawScanner()
    result = scanner.scan()

    if not result.found:
        console.print("[yellow]  OpenClaw:  ✗ Not found at ~/.openclaw[/]")
        console.print("  [dim]OA works best with OpenClaw. Install it at https://github.com/openclaw/openclaw[/]")
        console.print("  [dim]Continuing with empty config...[/]\n")
    else:
        console.print(f"  OpenClaw:  [green]✓[/] Found at {result.openclaw_home}")
        console.print(f"  Agents:    [green]✓[/] {len(result.agents)} agents detected")
        for agent in result.agents:
            active_str = ""
            if agent.last_active:
                active_str = f" [dim](last active: {_relative_time(agent.last_active)})[/]"
            console.print(f"             • {agent.id}{active_str}")
        enabled = sum(1 for j in result.cron_jobs if j.enabled)
        disabled = len(result.cron_jobs) - enabled
        console.print(f"  Cron:      [green]✓[/] {len(result.cron_jobs)} jobs ({enabled} enabled, {disabled} disabled)")
        console.print(f"  Sessions:  [green]✓[/] {result.session_count} session files")

    # Generate config
    config = ProjectConfig.from_scan(result)
    config.db_path = Path("data") / "monitor.db"

    console.print(f"\n[bright_magenta]📊 Setting up built-in goals:[/]")
    for goal in config.goals:
        if goal.builtin:
            console.print(f"  [green]✓[/] {goal.name} — {_goal_description(goal.id)}")

    # Optional goals prompt
    if not yes:
        console.print(f"\n[bright_magenta]📋 Optional goal templates:[/]")
        console.print("  [1] Knowledge Sharing — shared learnings growth")
        console.print("  [2] Custom goal")
        console.print("  [0] Skip — just use built-ins")
        # For now, default to skip (interactive prompts in v0.2)
        console.print("\n  [dim]Interactive goal selection coming in v0.2. Using built-ins only.[/]")

    # Create project
    project.mkdir(parents=True)
    (project / "data").mkdir()
    (project / "pipelines").mkdir()

    # Save config
    config_path = project / "config.yaml"
    config.save(config_path)

    # Create schema
    db_path = project / "data" / "monitor.db"
    create_schema(db_path)

    console.print(Panel(
        f"[green]✓[/] Created project [bold]{name}[/]\n\n"
        f"  [dim]config.yaml[/]          ← goals + agent list\n"
        f"  [dim]data/monitor.db[/]      ← SQLite database (schema ready)\n"
        f"  [dim]pipelines/[/]           ← custom pipeline scripts\n\n"
        f"Next steps:\n"
        f"  cd {name}\n"
        f"  oa collect    ← gather data now\n"
        f"  oa serve      ← open dashboard\n"
        f"  oa status     ← terminal health view",
        title="📊 OA — Operational Analytics",
        border_style="bright_magenta",
    ))


# ━━━ oa collect ━━━

@main.command()
@click.option("--goal", "-g", default=None, help="Collect for a specific goal only")
@click.option("--date", "-d", default=None, help="Date to collect for (YYYY-MM-DD)")
@click.option("--config", "-c", "config_path", default="config.yaml", help="Config file path")
def collect(goal: str | None, date: str | None, config_path: str):
    """Run data collection pipelines."""
    from .core.config import ProjectConfig
    from .pipelines.cron_reliability import CronReliabilityPipeline

    config_file = Path(config_path)
    if not config_file.exists():
        console.print("[red]Error:[/] config.yaml not found. Run `oa init` first.")
        raise SystemExit(1)

    config = ProjectConfig.load(config_file)
    date_str = date or datetime.now().strftime("%Y-%m-%d")

    console.print(f"\n[bright_magenta]📊 Collecting data for {date_str}...[/]\n")

    from .pipelines.viking_activity import VikingActivityPipeline
    from .pipelines.knowledge_growth import KnowledgeGrowthPipeline
    from .pipelines.conversation_quality import ConversationQualityPipeline
    from .pipelines.heartbeat_bridge import HeartbeatBridgePipeline
    from .pipelines.infra_health import InfraHealthPipeline

    builtin_pipelines = {
        "cron_reliability": CronReliabilityPipeline(),
        "team_health": VikingActivityPipeline(),
        "knowledge_growth": KnowledgeGrowthPipeline(),
        "conversation_quality": ConversationQualityPipeline(),
        "heartbeat_status": HeartbeatBridgePipeline(),
        "infra_health": InfraHealthPipeline(),
    }

    for goal_config in config.goals:
        if goal and goal_config.id != goal:
            continue

        pipeline = builtin_pipelines.get(goal_config.id)
        if not pipeline and not goal_config.builtin:
            console.print(f"  [yellow]⊘[/] {goal_config.name} — custom pipeline (not yet supported)")
            continue
        if not pipeline:
            console.print(f"  [yellow]⊘[/] {goal_config.name} — no pipeline registered")
            continue

        console.print(f"  [bright_magenta]{goal_config.name}[/]")

        db = None
        try:
            metrics = pipeline.collect(date_str, config)

            db = sqlite3.connect(str(config.db_path))
            db.execute("PRAGMA journal_mode=WAL")
            for m in metrics:
                breakdown_json = json.dumps(m.breakdown) if m.breakdown else None
                db.execute(
                    """INSERT INTO goal_metrics (date, goal, metric, value, unit, breakdown)
                       VALUES (?, ?, ?, ?, ?, ?)
                       ON CONFLICT(date, goal, metric) DO UPDATE SET
                           value = excluded.value, breakdown = excluded.breakdown,
                           created_at = datetime('now')""",
                    (date_str, goal_config.id, m.name, m.value, m.unit, breakdown_json),
                )
                sep = " " if m.unit and not m.unit.startswith("%") else ""
                console.print(f"    [green]✓[/] {m.name}: {m.value}{sep}{m.unit}")
            db.commit()

        except Exception as e:
            console.print(f"    [red]✗[/] Error: {e}")
        finally:
            if db:
                db.close()

    console.print(f"\n[green]✓[/] Results written to {config.db_path}")


# ━━━ oa heal ━━━

@main.command()
@click.option("--config", "-c", "config_path", default="config.yaml", help="Config file path")
@click.option("--dry-run", is_flag=True, help="Diagnose only, don't execute actions")
@click.option("--safe-only", is_flag=True, help="Only execute safe actions, skip risky")
@click.option("--send-report", is_flag=True, help="Send report to Feishu after heal")
def heal(config_path: str, dry_run: bool, safe_only: bool, send_report: bool):
    """Diagnose anomalies and auto-fix safe issues."""
    from .heal import run_heal

    config_file = Path(config_path)
    if not config_file.exists():
        console.print("[red]Error:[/] config.yaml not found.")
        raise SystemExit(1)

    mode = "DRY RUN" if dry_run else ("SAFE ONLY" if safe_only else "FULL")
    console.print(f"\n[bright_magenta]🔧 OA Self-Improvement ({mode})...[/]\n")

    report = run_heal(config_path=str(config_file), dry_run=dry_run, safe_only=safe_only)

    executed = [a for a in report.actions if a.executed]
    risky = [a for a in report.actions if a.level == "risky" and not a.executed]
    suggestions = [a for a in report.actions if not a.executed and a.level == "safe"]

    if executed:
        console.print(f"  [green]Executed ({len(executed)}):[/]")
        for a in executed:
            freed = f" [dim]({a.bytes_freed // 1024 // 1024}MB freed)[/]" if a.bytes_freed > 0 else ""
            console.print(f"    [green]✓[/] {a.title}{freed}")
            if a.result:
                console.print(f"      [dim]{a.result}[/]")

    if risky:
        console.print(f"\n  [yellow]Needs Confirmation ({len(risky)}):[/]")
        for a in risky:
            console.print(f"    [yellow]![/] {a.title}")
            console.print(f"      [dim]{a.detail}[/]")

    if suggestions:
        console.print(f"\n  [blue]Suggestions ({len(suggestions)}):[/]")
        for a in suggestions:
            console.print(f"    [blue]-[/] {a.title}")

    if report.suggestions:
        console.print(f"\n  [blue]Improvement Tips:[/]")
        for s in report.suggestions:
            console.print(f"    [blue]-[/] {s}")

    total_freed = sum(a.bytes_freed for a in executed)
    if total_freed > 0:
        console.print(f"\n  [green]Storage freed: {total_freed // 1024 // 1024}MB[/]")

    if send_report:
        import yaml
        with open(config_file, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
        from .feishu_reporter import _get_feishu_credentials, _get_token, _send_message
        creds = _get_feishu_credentials()
        if creds:
            token = _get_token(creds[0], creds[1])
            _send_message(token, creds[2], report.summary_text())
            console.print(f"\n  [green]✓[/] Report sent to Feishu")
        else:
            console.print(f"\n  [red]x[/] Feishu credentials not found")

    console.print()


# ━━━ oa serve ━━━

@main.command()
@click.option("--port", "-p", default=3460, help="Port to serve on")
@click.option("--config", "-c", "config_path", default="config.yaml", help="Config file path")
@click.option("--no-open", is_flag=True, help="Don't open browser automatically")
def serve(port: int, config_path: str, no_open: bool):
    """Start the OA dashboard in your browser."""
    from .server import serve as start_server

    config_file = Path(config_path)
    if not config_file.exists():
        console.print("[red]Error:[/] config.yaml not found. Run `oa init` first.")
        raise SystemExit(1)

    start_server(port=port, config_path=config_path, open_browser=not no_open)


# ━━━ oa status ━━━

@main.command()
@click.option("--config", "-c", "config_path", default="config.yaml", help="Config file path")
def status(config_path: str):
    """Show current goal health in the terminal."""
    from .core.config import ProjectConfig

    config_file = Path(config_path)
    if not config_file.exists():
        console.print("[red]Error:[/] config.yaml not found. Run `oa init` first.")
        raise SystemExit(1)

    config = ProjectConfig.load(config_file)

    if not config.db_path.exists():
        console.print("[yellow]No data yet.[/] Run `oa collect` first.")
        raise SystemExit(0)

    db = sqlite3.connect(str(config.db_path))

    table = Table(title="📊 OA — System Health", border_style="bright_magenta")
    table.add_column("Goal", style="bold")
    table.add_column("Metric", style="dim")
    table.add_column("Value", justify="right")
    table.add_column("Status", justify="center")

    for goal_config in config.goals:
        for metric_config in goal_config.metrics:
            row = db.execute(
                """SELECT value, unit FROM goal_metrics
                   WHERE goal = ? AND metric = ?
                   ORDER BY date DESC LIMIT 1""",
                (goal_config.id, metric_config.name),
            ).fetchone()

            if row:
                value, unit = row
                sep = " " if unit and not unit.startswith("%") else ""
                value_str = f"{value}{sep}{unit}"
                status_str = _health_status(value, metric_config.healthy, metric_config.warning)
            else:
                value_str = "—"
                status_str = "[dim]no data[/]"

            table.add_row(goal_config.name, metric_config.name, value_str, status_str)

    db.close()
    console.print()
    console.print(table)
    console.print()


# ━━━ oa report ━━━

@main.command()
@click.option("--config", "-c", "config_path", default="config.yaml", help="Config file path")
@click.option("--date", "-d", default=None, help="Date to report (YYYY-MM-DD)")
@click.option("--dry-run", is_flag=True, help="Print report without sending to Feishu")
def report(config_path: str, date: str | None, dry_run: bool):
    """Send daily health report to Feishu."""
    import yaml
    from .feishu_reporter import build_health_report, send_daily_report

    config_file = Path(config_path)
    if not config_file.exists():
        console.print("[red]Error:[/] config.yaml not found. Run `oa init` first.")
        raise SystemExit(1)

    with open(config_file, encoding="utf-8") as f:
        config_data = yaml.safe_load(f) or {}

    db_path = Path(config_data.get("db_path", "data/monitor.db"))
    if not db_path.is_absolute():
        db_path = (config_file.parent / db_path).resolve()

    date_str = date or datetime.now().strftime("%Y-%m-%d")
    report_text = build_health_report(db_path, config_data, date_str)

    if dry_run:
        console.print(Panel(report_text, title="📊 Health Report (dry run)", border_style="bright_magenta"))
        return

    console.print(f"\n[bright_magenta]📤 Sending report for {date_str} to Feishu...[/]\n")
    success = send_daily_report(db_path, config_data, date_str)

    if success:
        console.print("[green]✓[/] Report sent to Feishu successfully!")
    else:
        console.print("[red]✗[/] Failed to send report. Check Feishu credentials in openclaw.json.")
        console.print("\n[dim]Report content:[/]")
        console.print(report_text)


# ━━━ oa doctor ━━━

@main.command()
def doctor():
    """Check system dependencies."""
    import sys
    import shutil

    console.print("\n[bright_magenta]🩺 OA Doctor — Checking dependencies...[/]\n")

    # Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)
    console.print(f"  Python:    {'[green]✓[/]' if py_ok else '[red]✗[/]'} {py_ver}"
                  + ("" if py_ok else " [red](need 3.10+)[/]"))

    # SQLite
    try:
        import sqlite3 as _
        console.print("  SQLite:    [green]✓[/] available")
    except ImportError:
        console.print("  SQLite:    [red]✗[/] not available")

    # OpenClaw
    openclaw_home = Path.home() / ".openclaw"
    if openclaw_home.exists():
        console.print(f"  OpenClaw:  [green]✓[/] found at {openclaw_home}")
    else:
        console.print("  OpenClaw:  [yellow]⊘[/] not found at ~/.openclaw")

    # Cron jobs
    jobs_file = openclaw_home / "cron" / "jobs.json"
    if jobs_file.exists():
        console.print(f"  Cron data: [green]✓[/] jobs.json found")
    else:
        console.print("  Cron data: [yellow]⊘[/] no cron/jobs.json")

    # OA project
    config_file = Path("config.yaml")
    if config_file.exists():
        console.print("  OA project:[green]✓[/] config.yaml found in current directory")
    else:
        console.print("  OA project:[dim] ⊘ no config.yaml (run `oa init`)[/]")

    console.print()


# ━━━ oa cron ━━━

@main.group()
def cron():
    """Cron job management."""
    pass


@cron.command(name="show")
def cron_show():
    """Show suggested cron schedule for OpenClaw."""
    cron_config = {
        "name": "oa-collect",
        "schedule": {"kind": "cron", "expr": "0 7,12,19 * * *"},
        "sessionTarget": "isolated",
        "payload": {
            "kind": "agentTurn",
            "message": "Run `oa collect` in the OA project directory and report results.",
        },
        "delivery": {"mode": "announce"},
        "enabled": True,
    }

    console.print("\n[bright_magenta]📋 Suggested cron schedule for OpenClaw:[/]\n")
    console.print("  Add this to your OpenClaw cron config:\n")
    console.print(f"  [bold]{json.dumps(cron_config, indent=2)}[/]")
    console.print("\n  This collects metrics 3x daily at 7:00 AM, 12:00 PM, and 7:00 PM.\n")
    console.print("  [dim]Or add to system crontab:[/]")
    console.print("  [dim]0 7,12,19 * * * cd /path/to/oa-project && oa collect[/]\n")


# ━━━ Helpers ━━━

def _health_status(value: float, healthy: float, warning: float) -> str:
    """Return colored health status string."""
    if value >= healthy:
        return "[green]● healthy[/]"
    elif value >= warning:
        return "[yellow]● warning[/]"
    else:
        return "[red]● critical[/]"


def _goal_description(goal_id: str) -> str:
    """Return human description for built-in goals."""
    descriptions = {
        "cron_reliability": "success rate across all cron jobs",
        "team_health": "daily agent activity and memory discipline",
    }
    return descriptions.get(goal_id, "")


def _relative_time(iso_timestamp: str) -> str:
    """Convert ISO timestamp to relative time string."""
    try:
        dt = datetime.fromisoformat(iso_timestamp)
        now = datetime.now()
        diff = now - dt
        if diff.days > 0:
            return f"{diff.days}d ago"
        hours = diff.seconds // 3600
        if hours > 0:
            return f"{hours}h ago"
        minutes = diff.seconds // 60
        return f"{minutes}m ago"
    except (ValueError, TypeError):
        return "unknown"


if __name__ == "__main__":
    main()
