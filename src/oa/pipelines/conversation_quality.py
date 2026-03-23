"""Conversation Quality pipeline — tracks message processing from queue.db."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from .base import Metric, Pipeline
from .viking_activity import _find_queue_db

if TYPE_CHECKING:
    from oa.core.config import ProjectConfig


class ConversationQualityPipeline(Pipeline):
    """Tracks queue message throughput, processing success rate, and latency."""

    goal_id = "conversation_quality"

    def collect(self, date: str, config: "ProjectConfig") -> list[Metric]:
        from oa.core.tracing import Tracer
        tracer = Tracer(service="conversation_quality", db_path=config.db_path)

        with tracer.span("Conversation Quality", {"date": date}) as root:
            queue_db = _find_queue_db(config.openclaw_home)

            total = 0
            completed = 0
            pending = 0
            processing = 0

            if queue_db:
                with tracer.span("Read Queue Stats"):
                    try:
                        dt_start = datetime.strptime(date, "%Y-%m-%d")
                        dt_end = dt_start + timedelta(days=1)
                        ts_start = int(dt_start.timestamp())
                        ts_end = int(dt_end.timestamp())

                        db = sqlite3.connect(str(queue_db))
                        rows = db.execute(
                            "SELECT status, COUNT(*) FROM queue_messages "
                            "WHERE timestamp >= ? AND timestamp < ? GROUP BY status",
                            (ts_start, ts_end),
                        ).fetchall()

                        for status, count in rows:
                            total += count
                            if status == "completed":
                                completed += count
                            elif status == "pending":
                                pending += count
                            elif status == "processing":
                                processing += count

                        db.close()
                    except Exception:
                        pass

            success_rate = round(completed / total * 100, 1) if total > 0 else 100.0
            if total == 0 and pending == 0:
                success_rate = 0

            pending_ratio = round(pending / total * 100, 1) if total > 0 else 0

            root.set_attribute("total", total)
            root.set_attribute("success_rate", success_rate)

        tracer.flush()
        return [
            Metric("message_throughput", total, unit="count",
                   breakdown={"completed": completed, "pending": pending, "processing": processing}),
            Metric("processing_success_rate", success_rate, unit="%"),
            Metric("pending_ratio", pending_ratio, unit="%"),
        ]
