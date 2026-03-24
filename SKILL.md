---
name: oa-cli
description: AI Agent 团队运维分析与自动改进工具。监控 Cron 可靠性、Agent 健康度、知识增长、对话质量、心跳状态、基础设施。自动诊断异常并修复安全问题。当用户提到 oa、运维分析、系统健康、oa collect、oa heal、oa serve、oa status、oa report 时使用此技能。
---

# OA — Operational Analytics & Self-Improvement

AI Agent 团队运维分析 + 自动改进系统。监控 7 个目标 × 19 个指标，9 项自动改进动作。

## 执行方式

使用包装脚本（确保 Python PATH 正确）：

```cmd
%USERPROFILE%\.openclaw\workspace\skills\oa-cli\scripts\oa-collect.cmd
%USERPROFILE%\.openclaw\workspace\skills\oa-cli\scripts\oa-report.cmd
%USERPROFILE%\.openclaw\workspace\skills\oa-cli\scripts\oa-full-cycle.cmd
```

或直接调用 CLI（需 Python 在 PATH 中）：

```bash
oa collect --config ~/.openclaw/workspace/oa-project/config.yaml
oa heal --config ~/.openclaw/workspace/oa-project/config.yaml
oa status --config ~/.openclaw/workspace/oa-project/config.yaml
oa report --config ~/.openclaw/workspace/oa-project/config.yaml
oa serve --config ~/.openclaw/workspace/oa-project/config.yaml
```

## CLI 命令

| 命令 | 说明 |
|------|------|
| `oa collect` | 采集全部 7 个目标的指标数据 |
| `oa heal` | 自动诊断 + 修复安全问题，危险操作飞书通知 |
| `oa heal --safe-only` | 只执行安全操作 |
| `oa heal --dry-run` | 只诊断不执行 |
| `oa heal --send-report` | 执行后发送改进报告到飞书 |
| `oa status` | 终端查看健康状态表格 |
| `oa report` | 发送健康报告到飞书 |
| `oa serve` | 启动 Dashboard (localhost:3460) |
| `oa doctor` | 检查系统依赖 |
| `oa cron show` | 显示建议 Cron 配置 |

## 标准化流水线

| 时段 | 脚本 | 流程 |
|------|------|------|
| 早 07:00 | oa-collect.cmd | collect + heal(safe-only) |
| 午 12:00 | oa-collect.cmd | collect + heal(safe-only) |
| 晚 19:00 | oa-full-cycle.cmd | collect + heal(full) + report |

## 7 个监控目标

1. **Cron Reliability** — 定时任务成功率
2. **Team Health** — Agent 活跃数 + 记忆纪律
3. **Knowledge Growth** — 记忆数 + 技能数 + AutoSkill
4. **Conversation Quality** — 消息量 + 每会话消息数 + 活跃 Agent
5. **Heartbeat Status** — 心跳存活率 + 待办完成率 + Cron 健康
6. **Infrastructure Health** — 向量库体积 + Gateway 存活 + 会话存储
7. **Self Improvement** — heal 得分 + token 消耗 + 记忆重复 + 过长对话 + 技能缺失

## 9 项自动改进动作

| 动作 | 安全级别 | 说明 |
|------|---------|------|
| Session 清理 | SAFE 自动 | 清理 >7天的归档 session 文件 |
| Cron 健康检查 | SAFE 自动 | 检测 OA cron 配置问题 |
| 技能巡检 | SAFE 自动 | 标记缺 SKILL.md 和过期技能 |
| 知识整理 | SAFE 自动 | AutoSkill 超 80 个时清理 |
| 路径监控 | SAFE 自动 | 扫描 config 所有路径是否可达 |
| 模型成本分析 | SAFE 分析 | 统计 token 消耗分布 |
| 对话质量检查 | SAFE 分析 | 标记过长 session |
| 记忆优化 | RISKY 通知 | 扫描重复记忆，不自动删除 |
| Gateway 守护 | RISKY 通知 | 检测停止后飞书通知 |

## Dashboard

- 地址: http://localhost:3460
- 中英文切换: 右上角按钮
- 自动改进状态栏: heal 得分 + token 饼图
- 30 秒自动刷新

## 目录结构

```
skills/oa-cli/
├── src/oa/
│   ├── cli.py                  # CLI 入口
│   ├── heal.py                 # 自动改进引擎
│   ├── server.py               # Dashboard 服务器
│   ├── feishu_reporter.py      # 飞书推送
│   ├── core/                   # 配置、Schema、追踪
│   ├── pipelines/              # 7 个数据管线
│   ├── actions/                # 9 个改进动作
│   └── dashboard/              # 预构建 React Dashboard
├── dashboard-src/              # Dashboard TypeScript 源码
├── scripts/                    # Windows 包装脚本
├── templates/                  # 配置模板
└── tests/                      # 测试套件
```
