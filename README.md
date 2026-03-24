# OA — Operational Analytics & Self-Improvement for OpenClaw

OA is an operational analytics CLI and self-improvement system for [OpenClaw](https://github.com/openclaw/openclaw) AI agent teams. It monitors your agents' health, tracks knowledge growth, analyzes model costs, and **automatically fixes safe issues** — all from the command line or a local Dashboard.

## What It Does

OA answers one question: **Is your AI agent team getting better?**

- **7 monitoring goals** with 21 metrics, tracked daily
- **9 self-improvement actions** that auto-diagnose and fix issues
- **Local Dashboard** with Chinese/English toggle, trend charts, and token cost pie chart
- **Feishu integration** for daily health reports and alerts
- **OTel-compatible tracing** for every data pipeline

### Monitoring Goals

| Goal | What It Tracks | Key Metrics |
|------|---------------|-------------|
| **Cron Reliability** | Are scheduled tasks succeeding? | success_rate (%) |
| **Team Health** | How many agents are active today? | active_agent_count, memory_discipline |
| **Knowledge Growth** | Is the system learning? | total_memories, daily_new, skills_count, autoskill_sessions |
| **Conversation Quality** | How are conversations going? | message_throughput, unanswered_sessions, failed_sessions |
| **Heartbeat Status** | Are agents alive and tasks on track? | heartbeat_alive_rate, todo_completion, cron_health |
| **Infrastructure Health** | Is the system infrastructure OK? | vectordb_size_kb, gateway_alive, session_storage_mb |
| **Self-Improvement** | How well is auto-healing working? | heal_score, daily_tokens, memory_duplicates, long_sessions |

### Self-Improvement Actions

| Action | Safety Level | What It Does |
|--------|-------------|-------------|
| Session cleanup | **SAFE** (auto) | Deletes archived `.reset`/`.deleted`/`.bak` session files older than 7 days |
| Cron self-heal | **SAFE** (auto) | Detects failed OA cron jobs, reports PATH/timeout issues |
| Skill audit | **SAFE** (auto) | Flags skills missing SKILL.md, marks stale skills (>30 days) |
| Knowledge tidy | **SAFE** (auto) | Cleans expired AutoSkill sessions when count exceeds 80 |
| Path monitor | **SAFE** (auto) | Scans all config paths for broken references or non-root pointers |
| Model cost analysis | **SAFE** (analysis) | Extracts token usage per model from cron JSONL, writes to Dashboard |
| Conversation quality | **SAFE** (analysis) | Flags sessions with >100 messages, suggests /compress |
| Memory optimization | **RISKY** (notify) | Scans for duplicate memories, sends report — never auto-deletes |
| Gateway guard | **RISKY** (notify) | Detects gateway down, notifies owner via Feishu for restart |

## Installation

### Prerequisites

- **Python 3.10+** with pip
- **OpenClaw** installed at `~/.openclaw/`
- **Node.js** (only if modifying Dashboard UI)

### Install

```bash
# Clone
git clone https://github.com/zhangzeyu99-web/oa-cli.git
cd oa-cli

# Install as editable package
pip install -e .

# Verify
oa --version
oa doctor
```

### Initialize a project

```bash
# Auto-detect your OpenClaw setup
oa init my-analytics --yes
cd my-analytics

# Or manually create config
mkdir -p ~/.openclaw/workspace/oa-project/data
# Copy templates/config.yaml to ~/.openclaw/workspace/oa-project/config.yaml
# Edit: set openclaw_home and db_path
```

### OpenClaw Skill Installation

To install as an OpenClaw skill (so your agents can use it):

```bash
# Copy to OpenClaw skills directory
cp -r oa-cli ~/.openclaw/workspace/skills/oa-cli

# Install Python package
pip install -e ~/.openclaw/workspace/skills/oa-cli

# Verify agent can access
oa doctor
```

## Usage

### Daily Commands

```bash
# Collect all metrics
oa collect --config path/to/config.yaml

# View health in terminal
oa status --config path/to/config.yaml

# Auto-diagnose and fix (safe actions only)
oa heal --config path/to/config.yaml --safe-only

# Full heal (safe auto-execute, risky notify via Feishu)
oa heal --config path/to/config.yaml

# Dry run (diagnose without executing)
oa heal --config path/to/config.yaml --dry-run

# Send health report to Feishu
oa report --config path/to/config.yaml

# Start Dashboard
oa serve --config path/to/config.yaml
# Open http://localhost:3460
```

### Automated Pipeline (Recommended)

Set up three daily cron jobs in OpenClaw:

| Time | Script | What It Does |
|------|--------|-------------|
| 07:00 | `scripts/oa-collect.cmd` | collect + heal (safe-only) |
| 12:00 | `scripts/oa-collect.cmd` | collect + heal (safe-only) |
| 19:00 | `scripts/oa-full-cycle.cmd` | collect + heal (full) + Feishu report |

Add to `~/.openclaw/cron/jobs.json`:

```json
{
  "id": "oa-collect-0700",
  "name": "OA Collect Morning",
  "schedule": {"kind": "cron", "expr": "0 7 * * *", "tz": "Asia/Shanghai"},
  "sessionTarget": "isolated",
  "payload": {
    "kind": "agentTurn",
    "message": "Run the OA collect script at ~/.openclaw/workspace/skills/oa-cli/scripts/oa-collect.cmd"
  },
  "enabled": true
}
```

### Agent Instructions

Add this to your agent's instructions or HEARTBEAT.md so the agent knows how to use OA:

```markdown
## OA Operational Analytics

When asked about system health, monitoring, or self-improvement:

1. Run: `oa collect --config ~/.openclaw/workspace/oa-project/config.yaml`
2. Run: `oa heal --safe-only --config ~/.openclaw/workspace/oa-project/config.yaml`
3. Run: `oa status --config ~/.openclaw/workspace/oa-project/config.yaml`

For full reports: `oa report --config ~/.openclaw/workspace/oa-project/config.yaml`
For Dashboard: `oa serve --config ~/.openclaw/workspace/oa-project/config.yaml`

If `oa` command not found, use the wrapper scripts:
- Collect: ~/.openclaw/workspace/skills/oa-cli/scripts/oa-collect.cmd
- Report: ~/.openclaw/workspace/skills/oa-cli/scripts/oa-report.cmd
- Full cycle: ~/.openclaw/workspace/skills/oa-cli/scripts/oa-full-cycle.cmd
```

## Dashboard

The Dashboard is a pre-built React app served by `oa serve`. No Node.js required for end users.

### Features

- **Chinese/English toggle** — click the flag icon in the top-right corner
- **6 goal cards** with sparkline trend charts (Self-Improvement shown as a status strip)
- **Token cost pie chart** — daily/weekly view with per-model breakdown
- **Self-Improvement status bar** — heal score, tokens, duplicates, long sessions, missing skills
- **Mechanism view** — SVG data flow diagrams for each pipeline
- **30-second auto-refresh**

### Modifying the Dashboard

```bash
cd dashboard-src
npm install
npm run dev      # Vite dev server with hot reload
npm run build    # Build to ../src/oa/dashboard/
```

Key files:
- `src/App.tsx` — main layout, language toggle
- `src/i18n.ts` — all Chinese/English translations
- `src/components/GoalCard.tsx` — metric cards
- `src/components/GoalDetailSection.tsx` — charts (Cron stacked bar, Team Health dual axis, default area)
- `src/components/HealStrip.tsx` — self-improvement status bar
- `src/components/TokenPieChart.tsx` — token cost pie chart
- `src/components/MechanismView.tsx` — data flow diagrams

## Configuration

### config.yaml

```yaml
openclaw_home: ~/.openclaw
db_path: data/monitor.db

agents:
  - id: main
    name: Main Agent
  - id: helper
    name: Helper

goals:
  - id: cron_reliability
    name: Cron Reliability
    builtin: true
    metrics:
      - name: success_rate
        unit: "%"
        healthy: 95    # green if >= 95%
        warning: 80    # yellow if >= 80%, red if below

  # For "lower is better" metrics (e.g. duplicates):
  - id: self_improvement
    name: Self Improvement
    builtin: true
    metrics:
      - name: memory_duplicates
        unit: count
        healthy: 10    # green if <= 10
        warning: 50    # yellow if <= 50, red if above
```

**Threshold logic**: If `healthy >= warning`, metric is "higher is better". If `healthy < warning`, metric is "lower is better".

**Agent aliases**: If an agent name in OpenClaw bindings maps to a different agentId (e.g. `bot-xiaoxia` → `agentId: main`), configure only the real agent in `agents` list. OA automatically excludes alias directories from activity scanning.

### Feishu Integration

OA reads Feishu bot credentials from `~/.openclaw/openclaw.json` automatically. The bot sends:
- Daily health reports via `oa report`
- Self-improvement reports via `oa heal --send-report`
- No configuration needed if OpenClaw is already connected to Feishu.

## Custom Pipelines

Create your own metrics by subclassing `Pipeline`:

```python
from oa import Pipeline, Metric

class MyPipeline(Pipeline):
    goal_id = "my_goal"

    def collect(self, date: str, config) -> list[Metric]:
        # Your logic here
        return [Metric("my_metric", 42, unit="count")]
```

Register in `cli.py`'s `builtin_pipelines` dict, add the goal to `config.yaml`, and run `oa collect`.

## Architecture

```
~/.openclaw/                        OA reads from:
├── cron/jobs.json          ──────► Job definitions + schedules
├── cron/runs/*.jsonl       ──────► Per-run success/failure + token usage
├── agents/*/sessions/      ──────► Session activity + message counts
├── workspace/skills/       ──────► Skill inventory
├── workspace/memory/       ──────► Knowledge files
├── autoskill/              ──────► AutoSkill sessions
├── data/vectordb/          ──────► OpenViking vector store
└── openclaw.json           ──────► Path health + Feishu credentials
                                           │
                                    6 Python Pipelines
                                           │
                                    SQLite Database
                                           │
                            ┌───────────────┼────────────────┐
                            │               │                │
                     Dashboard:3460    oa status       oa report
                     (React app)      (terminal)    (Feishu msg)
                            │
                     oa heal (9 actions)
                            │
                    ┌───────┴───────┐
                    SAFE            RISKY
                    (auto-fix)     (notify owner)
```

## Project Structure

```
oa-cli/
├── src/oa/                     # Python core
│   ├── cli.py                  # CLI entry (click)
│   ├── heal.py                 # Self-improvement engine
│   ├── server.py               # Dashboard HTTP server
│   ├── feishu_reporter.py      # Feishu message sender
│   ├── core/                   # Config, schema, scanner, tracing
│   ├── pipelines/              # 7 data collection pipelines
│   │   ├── cron_reliability.py
│   │   ├── viking_activity.py  # Team Health (reads .openclaw/agents)
│   │   ├── knowledge_growth.py
│   │   ├── conversation_quality.py
│   │   ├── heartbeat_bridge.py
│   │   └── infra_health.py
│   ├── actions/                # 9 self-improvement actions
│   │   ├── session_cleanup.py
│   │   ├── cron_heal.py
│   │   ├── skill_audit.py
│   │   ├── knowledge_tidy.py
│   │   ├── path_monitor.py
│   │   ├── gateway_guard.py
│   │   ├── cost_analysis.py
│   │   ├── conversation_quality_check.py
│   │   └── memory_optimize.py
│   └── dashboard/              # Pre-built React app (HTML+JS+CSS)
├── dashboard-src/              # React source (TypeScript + Tailwind)
├── scripts/                    # Windows batch wrappers for OpenClaw cron
├── templates/                  # Config and custom pipeline templates
├── tests/                      # Test suite
├── SKILL.md                    # OpenClaw skill manifest
├── pyproject.toml              # Python package config
└── LICENSE                     # MIT
```

## Safety Model

OA categorizes all actions into three levels:

| Level | Auto-Execute | Examples |
|-------|-------------|----------|
| **SAFE** | Yes | Clean archived sessions, flag missing skills, analyze costs |
| **RISKY** | No — Feishu notification first | Restart gateway, suggest memory cleanup |
| **BLOCKED** | Never | Delete skills, modify openclaw.json, kill processes |

The `oa heal` report clearly labels each action with `[auto]`, `[confirm]`, or `[blocked]`.

## License

MIT — Based on [Agent_Exploration/CLIs/oa-cli](https://github.com/Amyssjj/Agent_Exploration/tree/main/CLIs/oa-cli) by MotusAI.
