"""Gateway guard — detect gateway down, notify owner for restart."""
from __future__ import annotations
import socket
from pathlib import Path
from ..heal import Action, HealReport


def check_gateway(oc: Path, metrics: dict, report: HealReport, dry_run: bool) -> None:
    alive = False
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        alive = s.connect_ex(("127.0.0.1", 18789)) == 0
        s.close()
    except Exception:
        pass

    if alive:
        return

    gw_cmd = oc / "gateway.cmd"
    restart_hint = f"手动重启: {gw_cmd}" if gw_cmd.exists() else "gateway.cmd 未找到"

    action = Action(
        id="gateway_restart", category="gateway", level="risky",
        title="Gateway 已停止 (端口 18789 无响应)",
        detail=f"OpenClaw Gateway 不可达。{restart_hint}\n建议: 执行 gateway.cmd 重启。注意可能中断正在进行的对话。",
        metric="gateway_alive",
    )
    report.add(action)
