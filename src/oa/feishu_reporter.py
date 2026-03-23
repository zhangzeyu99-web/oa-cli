"""Feishu daily health report — sends OA status summary to Feishu after collection."""
from __future__ import annotations

import json
import sqlite3
import ssl
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


def _get_feishu_credentials() -> tuple[str, str, str] | None:
    """Read Feishu bot credentials from openclaw.json."""
    candidates = [
        Path("/mnt/d/project/openclaw/openclaw.json"),
        Path("D:/project/openclaw/openclaw.json"),
        Path.home() / ".openclaw" / "openclaw.json",
    ]
    for c in candidates:
        if c.exists():
            try:
                data = json.loads(c.read_text(encoding="utf-8"))
                channels = data.get("channels", {}).get("feishu", {})
                accounts = channels.get("accounts", {})
                bot = accounts.get("bot-xiaoxia", {})
                app_id = bot.get("appId", channels.get("appId", ""))
                app_secret = bot.get("appSecret", channels.get("appSecret", ""))
                allow_from = bot.get("groupAllowFrom", channels.get("groupAllowFrom", []))
                user_id = allow_from[0] if allow_from else ""
                if app_id and app_secret and user_id:
                    return app_id, app_secret, user_id
            except (json.JSONDecodeError, OSError, IndexError):
                continue
    return None


def _get_token(app_id: str, app_secret: str) -> str:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    body = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        data = json.loads(resp.read())
    return data["tenant_access_token"]


def _send_message(token: str, open_id: str, text: str) -> dict:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id"
    body = json.dumps({
        "receive_id": open_id,
        "msg_type": "text",
        "content": json.dumps({"text": text}),
    }).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    })
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        return json.loads(resp.read())


def build_health_report(db_path: Path, config_data: dict, date: str) -> str:
    """Build a text health report from the OA database."""
    db = sqlite3.connect(str(db_path))
    db.row_factory = sqlite3.Row

    lines = [
        f"📊 OA 每日健康报告 — {date}",
        "━" * 36,
    ]

    goals = config_data.get("goals", [])
    all_statuses = []

    for goal in goals:
        goal_id = goal["id"]
        goal_name = goal.get("name", goal_id)
        lines.append(f"\n🎯 {goal_name}")

        for m_cfg in goal.get("metrics", []):
            metric_name = m_cfg["name"]
            row = db.execute(
                "SELECT value, unit FROM goal_metrics WHERE goal=? AND metric=? AND date=?",
                (goal_id, metric_name, date),
            ).fetchone()

            if row:
                value, unit = row["value"], row["unit"]
                healthy = m_cfg.get("healthy", 0)
                warning = m_cfg.get("warning", 0)

                if value >= healthy:
                    icon, status = "🟢", "健康"
                elif value >= warning:
                    icon, status = "🟡", "警告"
                else:
                    icon, status = "🔴", "危险"

                all_statuses.append(status)
                sep = " " if unit and not unit.startswith("%") else ""
                lines.append(f"  {icon} {metric_name}: {value}{sep}{unit} ({status})")
            else:
                lines.append(f"  ⚪ {metric_name}: 无数据")
                all_statuses.append("无数据")

    # Agent activity
    agents = db.execute(
        "SELECT agent_id, session_count, memory_logged FROM daily_agent_activity WHERE date=?",
        (date,),
    ).fetchall()
    if agents:
        lines.append("\n👥 Agent 活跃度")
        for a in agents:
            icon = "✅" if a["session_count"] > 0 else "⬜"
            mem = "📝" if a["memory_logged"] else "  "
            lines.append(f"  {icon} {a['agent_id']} {mem}")

    # Overall
    if "危险" in all_statuses:
        overall = "🔴 系统需要关注"
    elif "警告" in all_statuses:
        overall = "🟡 部分指标需关注"
    elif any(s == "健康" for s in all_statuses):
        overall = "🟢 系统健康"
    else:
        overall = "⚪ 数据不足"

    lines.insert(2, f"\n{overall}")
    lines.append(f"\n━{'━' * 35}")
    lines.append(f"⏱️ 生成时间: {datetime.now().strftime('%H:%M:%S')}")
    lines.append("🔗 Dashboard: http://localhost:3460")

    db.close()
    return "\n".join(lines)


def send_daily_report(db_path: Path, config_data: dict, date: str) -> bool:
    """Send the daily health report to Feishu. Returns True on success."""
    creds = _get_feishu_credentials()
    if not creds:
        return False

    app_id, app_secret, user_id = creds
    report = build_health_report(db_path, config_data, date)

    try:
        token = _get_token(app_id, app_secret)
        result = _send_message(token, user_id, report)
        return result.get("code") == 0
    except Exception:
        return False
