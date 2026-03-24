"""Model cost analysis — extract token usage from session JSONL and cron runs."""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from ..heal import Action, HealReport


def analyze_cost(oc: Path, report: HealReport, date: str) -> None:
    model_usage: dict[str, dict[str, int]] = defaultdict(lambda: {"input": 0, "output": 0, "total": 0, "runs": 0})

    # From cron run JSONL
    runs_dir = oc / "cron" / "runs"
    if runs_dir.exists():
        for jf in runs_dir.glob("*.jsonl"):
            try:
                with open(jf, encoding="utf-8") as f:
                    for line in f:
                        try:
                            e = json.loads(line)
                            ts = e.get("ts") or e.get("runAtMs")
                            if ts and datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d") == date:
                                usage = e.get("usage", {})
                                model = e.get("model", "unknown")
                                provider = e.get("provider", "")
                                key = f"{provider}/{model}" if provider else model
                                model_usage[key]["input"] += usage.get("input_tokens", 0)
                                model_usage[key]["output"] += usage.get("output_tokens", 0)
                                model_usage[key]["total"] += usage.get("total_tokens", 0)
                                model_usage[key]["runs"] += 1
                        except (json.JSONDecodeError, OSError):
                            continue
            except OSError:
                continue

    if not model_usage:
        return

    total_tokens = sum(v["total"] for v in model_usage.values())
    lines = []
    for model, usage in sorted(model_usage.items(), key=lambda x: x[1]["total"], reverse=True):
        pct = round(usage["total"] / total_tokens * 100, 1) if total_tokens > 0 else 0
        lines.append(f"{model}: {usage['total']:,} tokens ({pct}%), {usage['runs']} runs")

    suggestions = []
    for model, usage in model_usage.items():
        if usage["total"] > 100000:
            suggestions.append(f"{model} 今日消耗 {usage['total']:,} tokens，考虑是否可用轻量模型替代")

    # Build per-model breakdown for Dashboard pie chart
    model_breakdown = {}
    for model, usage in sorted(model_usage.items(), key=lambda x: x[1]["total"], reverse=True):
        short_name = model.split("/")[-1] if "/" in model else model
        model_breakdown[short_name] = usage["total"]

    action = Action(
        id="cost_analysis", category="cost", level="safe",
        title=f"模型成本: 今日 {total_tokens:,} tokens, {sum(v['runs'] for v in model_usage.values())} 次调用",
        detail="\n".join(lines),
        executed=True,
        result=json.dumps({"total": total_tokens, "models": model_breakdown}, ensure_ascii=False),
    )
    report.add(action)

    for s in suggestions:
        report.suggestions.append(s)
