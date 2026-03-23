---
name: oa-cli
description: AI Agent 团队运维分析工具。用于监控 Cron 任务可靠性、Agent 团队健康度，提供 SQLite 数据存储和本地 Dashboard。当用户提到 oa、运维分析、cron 可靠性、agent 健康、oa collect、oa serve、oa status 时使用此技能。
---

# OA — Operational Analytics CLI

AI Agent 团队的运维分析 CLI 工具，可从命令行监控多 Agent 系统的运行状态。

## 架构

```text
OpenClaw 数据 → Python Pipelines → SQLite → Dashboard (localhost:3460)
```

**数据流：**
- `~/.openclaw/cron/jobs.json` + `runs/*.jsonl` → Cron 可靠性指标
- `~/.openclaw/sessions/` + Agent 内存文件 → 团队健康度指标
- 所有指标写入 SQLite → Dashboard 实时展示

## 前置条件

- Python 3.10+
- OpenClaw 已安装且运行
- 依赖：`click>=8.0`, `rich>=13.0`, `pyyaml>=6.0`

## 安装

```bash
cd /mnt/d/project/openclaw/skills/oa-cli
pip install -e .
```

或仅安装依赖：
```bash
pip install click rich pyyaml
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `oa init [项目名]` | 自动检测 OpenClaw 环境，创建分析项目 |
| `oa collect` | 运行所有数据采集管线 |
| `oa collect --goal cron_reliability` | 仅采集特定目标 |
| `oa serve` | 启动 Dashboard (localhost:3460) |
| `oa serve --port 8080` | 自定义端口 |
| `oa status` | 在终端显示当前健康状态 |
| `oa cron show` | 显示建议的 Cron 配置 |
| `oa doctor` | 检查系统依赖 |

## 内置目标

### G1: Cron Reliability（Cron 可靠性）

追踪 Cron 任务的实际成功率。

| 指标 | 说明 | 数据源 |
|------|------|--------|
| `success_rate` | 已调度槽位中成功完成的百分比 | `~/.openclaw/cron/runs/*.jsonl` |

### G2: Team Health（团队健康度）

追踪 Agent 每日活跃情况。

| 指标 | 说明 | 数据源 |
|------|------|--------|
| `active_agent_count` | 当天有会话活动的 Agent 数 | `~/.openclaw/sessions/` |
| `memory_discipline` | 记录了内存日志的 Agent 百分比 | Agent 内存文件 |

## 使用示例

### 初始化项目
```bash
oa init my-analytics --yes
cd my-analytics
```

### 采集数据
```bash
oa collect
```

### 查看健康状态
```bash
oa status
```

### 启动 Dashboard
```bash
oa serve
```

## 自定义目标

创建自定义管线：

```python
from oa import Pipeline, Metric

class ContentQuality(Pipeline):
    goal_id = "content_quality"

    def collect(self, date: str, config) -> list[Metric]:
        approved = count_approved(date)
        total = count_total(date)
        rate = approved / total * 100 if total else 0
        return [Metric("approval_rate", rate, unit="%")]
```

在 `config.yaml` 中注册后运行 `oa collect` 即可。

## Cron 自动化

```json
{
  "name": "oa-collect",
  "schedule": {"kind": "cron", "expr": "0 7,12,19 * * *"},
  "payload": {"kind": "agentTurn", "message": "Run `oa collect` and report results."}
}
```

## 与小虾的交互场景

> **用户**: 小虾，帮我看看系统健康状态

小虾执行 `oa status`，返回当前所有目标的健康指标。

> **用户**: 帮我采集一下今天的运维数据

小虾执行 `oa collect`，汇报 Cron 可靠性和团队健康度。

## 目录结构

```text
skills/oa-cli/
├── SKILL.md              # 本文件
├── pyproject.toml        # 项目构建配置
├── LICENSE               # MIT 许可证
├── README.md             # 原始英文文档
├── src/oa/               # 核心源码
│   ├── cli.py            # CLI 入口
│   ├── server.py         # Dashboard HTTP 服务器
│   ├── core/             # 核心模块
│   │   ├── config.py     # 配置管理
│   │   ├── scanner.py    # OpenClaw 自动检测
│   │   ├── schema.py     # SQLite Schema
│   │   └── tracing.py    # OTel 兼容追踪
│   ├── pipelines/        # 数据管线
│   │   ├── base.py       # Pipeline 基类
│   │   ├── cron_reliability.py  # G1: Cron 可靠性
│   │   └── team_health.py      # G2: 团队健康度
│   └── dashboard/        # 预构建 React Dashboard
├── templates/            # 配置模板
│   ├── config.yaml       # 配置文件模板
│   └── custom_pipeline.py  # 自定义管线模板
└── tests/                # 测试套件 (57 tests)
```

## 运行测试

```bash
cd /mnt/d/project/openclaw/skills/oa-cli
pip install -e ".[dev]"
pytest
```

## 技术说明

- 纯 Python，零运行时外部依赖（仅 click/rich/pyyaml）
- Dashboard 为预构建 React 应用（不需要 Node.js）
- OTel 兼容的 Trace 系统，Span 存入 SQLite
- 所有数据本地存储，无需云服务
