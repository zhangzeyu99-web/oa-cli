import { createContext, useContext } from "react";

export type Locale = "en" | "zh";

const dict: Record<Locale, Record<string, string>> = {
  en: {},
  zh: {
    // App
    "OA Dashboard": "OA 运维看板",
    "Is our machine getting better?": "我们的系统在变好吗？",
    "System Health": "系统健康",
    "Mechanism": "运行机制",
    "Loading": "加载中",
    "Connection Error": "连接失败",
    "Ensure the API server is running:": "请确保 API 服务正在运行：",
    "OA — Operational Analytics": "OA — 运维分析",

    // HealthSummaryStrip
    "Overall Health": "整体健康度",
    "No data": "暂无数据",

    // GoalDetailSection
    "Metrics": "📐 指标定义",
    "Metrics Definition": "指标定义",
    "Datasource:": "数据源：",
    "Definition": "定义",
    "Calculation": "计算方式",
    "Purpose": "用途",
    "Cron run tracking starting tomorrow": "Cron 运行追踪将于明天开始",
    "Combined chart will appear once per-slot data is recorded": "记录每个时间槽数据后图表将显示",
    "Team health data loading...": "团队健康数据加载中...",
    "Data collection starting soon": "数据采集即将开始",
    "Days Active per Agent": "每个 Agent 的活跃天数",

    // Chart legends
    "Succeeded": "成功",
    "Failed": "失败",
    "Missed": "缺失",
    "Success Rate": "成功率",
    "Active Agents": "活跃 Agent",
    "Sessions": "会话数",

    // MechanismView
    "How It Works": "运行原理",
    "Collect": "采集",
    "Data Pipeline": "数据管线",
    "Scans OpenClaw for cron runs, agent sessions, and memory files.":
      "扫描 OpenClaw 的 Cron 运行记录、Agent 会话和记忆文件。",
    "Analyze": "分析",
    "Goal Pipelines": "目标管线",
    "Runs each goal's pipeline to compute metrics, trends, and health status.":
      "运行各目标管线，计算指标、趋势和健康状态。",
    "Visualize": "可视化",
    "Dashboard": "仪表盘",
    "Serves real-time health cards, trend charts, and trace flows.":
      "提供实时健康卡片、趋势图和追踪流。",
    "Pipeline Traces": "🔭 管线追踪",
    "pipelines · latest runs": "条管线 · 最近运行",
    "Mechanism View — data flow + pipeline traces": "运行机制 — 数据流 + 管线追踪",

    // TracesView
    "No traces yet": "暂无追踪数据",
    "Run {cmd} to generate traces": "运行 {cmd} 生成追踪",

    // TraceFlowCard
    "Database": "数据库",
    "Script": "脚本",
    "Cron": "定时任务",
    "Agent": "Agent",
    "Source": "数据源",
    "Step": "步骤",
    "Success": "成功",
    "Traced": "已追踪",
    "spans": "Span",
    "Click to expand trace →": "点击展开追踪详情 →",
    "Execution Trace": "执行追踪",
    "Legend:": "图例：",

    // SystemHealth
    "No goals configured": "未配置目标",
    "Run {cmd} to set up goals": "运行 {cmd} 设置目标",

    // Metric names (snake_case → Chinese)
    "Success Rate_metric": "成功率",
    "Active Agent Count": "活跃 Agent 数",
    "Memory Discipline": "记忆纪律",
    "Total Memories": "总记忆数",
    "Daily New Memories": "今日新增记忆",
    "Queue Throughput": "已安装技能",
    "Vectordb Documents": "AI 自学会话",
    "Message Throughput": "消息吞吐量",
    "Processing Success Rate": "每会话消息数",
    "Pending Ratio": "活跃对话 Agent 数",
    "Unanswered Sessions": "无回复会话",
    "Failed Sessions": "失败会话",
    "Heartbeat Alive Rate": "心跳存活率",
    "Todo Completion": "待办完成率",
    "Reports Generated": "报告生成数",

    // Goal names
    "Cron Reliability": "Cron 可靠性",
    "Team Health": "团队健康度",
    "Knowledge Growth": "知识增长",
    "Conversation Quality": "对话质量",
    "Heartbeat Status": "心跳状态",
    "Infrastructure Health": "系统基础设施",
    "Self Improvement": "自我改进",

    // Self-improvement metrics
    "Heal Score": "改进得分",
    "Daily Tokens": "今日 Tokens",
    "Memory Duplicates": "记忆重复",
    "Long Sessions": "过长对话",
    "Skills Missing Doc": "技能缺失",

    // Infra metric names
    "Vectordb Size Kb": "向量库体积(KB)",
    "Gateway Alive": "网关存活",
    "Session Storage Mb": "会话存储(MB)",

    // Metric definitions (cron)
    "Percentage of cron jobs that ran and completed without error":
      "Cron 任务成功运行且无报错的百分比",
    "Succeeded ÷ (Total − Skipped) × 100":
      "成功数 ÷ (总数 − 跳过数) × 100",
    "Core reliability signal — are automated tasks running as scheduled?":
      "核心可靠性信号 — 自动化任务是否按计划运行？",
    "Cron job ran and completed without error":
      "Cron 任务已运行且无报错",
    "Count of runs with status='ok'":
      "状态为 'ok' 的运行次数",
    "Baseline count of healthy executions":
      "健康执行的基准计数",
    "Cron job ran but errored (timeout, crash, or exception)":
      "Cron 任务运行但出错（超时、崩溃或异常）",
    "Count of runs with status='error'":
      "状态为 'error' 的运行次数",
    "Identifies broken automation requiring fix":
      "识别需要修复的自动化问题",
    "Scheduled time slot with no run attempt recorded":
      "计划的时间槽内无运行记录",
    "Expected slots − Actual runs (within 900s match window)":
      "预期槽位数 − 实际运行数（900秒匹配窗口内）",
    "Detects silent failures where crons don't even start":
      "检测 Cron 任务未启动的静默故障",

    // Metric definitions (team health)
    "#DAA (Daily Active Agents)": "#DAA（每日活跃 Agent）",
    "Number of agents with status='active' per day":
      "每天状态为 'active' 的 Agent 数",
    "COUNT(agent_id WHERE session_count > 0) per date":
      "COUNT(agent_id WHERE session_count > 0) 按日期",
    "Daily team engagement — how many agents are working each day?":
      "每日团队参与度 — 每天有多少 Agent 在工作？",
    "Sessions per Day": "每日会话数",
    "Total sessions across all agents per day":
      "所有 Agent 每日总会话数",
    "SUM(session_count) per date from daily_agent_activity":
      "SUM(session_count) 按日期（daily_agent_activity 表）",
    "Activity volume — overall session throughput":
      "活动量 — 整体会话吞吐量",
    "Memory Logged": "记忆日志",
    "Number of agents that wrote memory files per day":
      "每天记录记忆文件的 Agent 数",
    "COUNT(agent_id WHERE memory_logged > 0) per date":
      "COUNT(agent_id WHERE memory_logged > 0) 按日期",
    "Are agents recording their work?":
      "Agent 是否在记录工作内容？",
    "Per-Agent Activity (bar chart)": "每 Agent 活跃度（柱状图）",
    "Days active vs days with sessions per agent":
      "每个 Agent 的活跃天数 vs 有会话天数",
    "COUNT(dates) GROUP BY agent_id":
      "COUNT(dates) GROUP BY agent_id",
    "Compare agent consistency over time":
      "对比 Agent 在时间维度上的一致性",
  },
};

export function t(key: string, locale: Locale): string {
  if (locale === "en") return key;
  return dict.zh[key] || key;
}

export function tMetric(snakeName: string, locale: Locale): string {
  const formatted = snakeName.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  if (locale === "en") return formatted;
  return dict.zh[formatted] || formatted;
}

export function tGoal(name: string, locale: Locale): string {
  if (locale === "en") return name;
  return dict.zh[name] || name;
}

export interface I18nCtx {
  locale: Locale;
  t: (key: string) => string;
  tMetric: (name: string) => string;
  tGoal: (name: string) => string;
  toggle: () => void;
}

export const I18nContext = createContext<I18nCtx>({
  locale: "zh",
  t: (k) => k,
  tMetric: (k) => k,
  tGoal: (k) => k,
  toggle: () => {},
});

export const useI18n = () => useContext(I18nContext);
