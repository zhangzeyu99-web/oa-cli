"""Path health monitor — scan all config paths for existence and consistency."""
from __future__ import annotations
import json
import re
from pathlib import Path
from ..heal import Action, HealReport


def check_paths(oc: Path, report: HealReport, dry_run: bool) -> None:
    config_file = oc / "openclaw.json"
    if not config_file.exists():
        report.add(Action(
            id="path_missing_config", category="path", level="risky",
            title="openclaw.json 不存在",
            detail=f"预期路径: {config_file}",
        ))
        return

    raw = config_file.read_text(encoding="utf-8")
    cfg = json.loads(raw)
    broken: list[str] = []
    non_root: list[str] = []

    # Check agent paths
    for agent in cfg.get("agents", {}).get("list", []):
        for k in ("workspace", "agentDir"):
            v = agent.get(k, "")
            if v:
                if not Path(v).exists():
                    broken.append(f"agent.{agent['id']}.{k}: {v}")
                if "/root/" in v or "/mnt/d/" in v or "D:/project/" in v:
                    non_root.append(f"agent.{agent['id']}.{k}: {v}")

    # Check plugin paths
    for name, info in cfg.get("plugins", {}).get("installs", {}).items():
        for k in ("installPath", "sourcePath"):
            v = info.get(k, "")
            if v and not Path(v).exists():
                broken.append(f"plugin.{name}.{k}: {v}")

    for p in cfg.get("plugins", {}).get("load", {}).get("paths", []):
        if not Path(p).exists():
            broken.append(f"plugins.load.path: {p}")

    # Check autoskill paths
    ask = cfg.get("plugins", {}).get("entries", {}).get("autoskill-openclaw-adapter", {}).get("config", {})
    for k, v in ask.get("embedded", {}).items():
        if isinstance(v, str) and ("/" in v or "\\" in v):
            if not Path(v).exists():
                broken.append(f"autoskill.{k}: {v}")

    # Check gateway.cmd node path
    gw = oc / "gateway.cmd"
    if gw.exists():
        for line in gw.read_text(encoding="utf-8").splitlines():
            for token in line.split():
                if "node" in token.lower() and token.endswith(".exe"):
                    if not Path(token).exists():
                        broken.append(f"gateway.cmd node: {token}")

    # Check ov.conf workspace
    ov_conf = Path.home() / ".openviking" / "ov.conf"
    if ov_conf.exists():
        try:
            ovc = json.loads(ov_conf.read_text(encoding="utf-8"))
            ws = ovc.get("storage", {}).get("workspace", "")
            if ws and not Path(ws).exists():
                broken.append(f"ov.conf workspace: {ws}")
        except (json.JSONDecodeError, OSError):
            pass

    # Check junction health
    if oc.is_dir():
        try:
            resolved = oc.resolve()
            if not resolved.exists():
                broken.append(f".openclaw junction broken: {oc} -> {resolved}")
        except OSError:
            broken.append(f".openclaw resolve failed")

    # Scan for non-.openclaw references
    for m in re.finditer(r'"([^"]*(?:/root/|/mnt/d/|D:\\\\project|D:/project)[^"]*)"', raw):
        non_root.append(m.group(1))

    # Check wrapper scripts
    for script in ["oa-collect.cmd", "oa-report.cmd"]:
        sp = oc / "workspace" / "skills" / "oa-cli" / "scripts" / script
        if not sp.exists():
            broken.append(f"OA script missing: {sp}")

    issues = []
    if broken:
        issues.append(f"断裂路径 ({len(broken)}): " + "; ".join(broken[:5]))
    if non_root:
        issues.append(f"非根目录引用 ({len(non_root)}): " + "; ".join(non_root[:3]))

    if not issues:
        action = Action(
            id="path_monitor", category="path", level="safe",
            title="路径健康检查: 全部正常",
            detail=f"检查了 openclaw.json + gateway.cmd + ov.conf, 无异常",
            executed=True,
            result="所有路径可达",
        )
        report.add(action)
        return

    level = "risky" if broken else "safe"
    action = Action(
        id="path_monitor", category="path", level=level,
        title=f"路径异常: {len(broken)} 断裂, {len(non_root)} 非根引用",
        detail="\n".join(issues),
    )
    if not broken:
        action.executed = True
        action.result = "非根引用已标记，无断裂路径"
    report.add(action)
