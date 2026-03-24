import { useState } from "react";
import { motion } from "framer-motion";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import type { GoalSummary } from "../types";
import { useI18n } from "../i18n";

const COLORS = ["#60A5FA", "#34D399", "#FBBF24", "#F87171", "#A78BFA", "#FB7185", "#22D3EE"];

interface Props {
  goals: GoalSummary[];
  goalMetrics: Record<string, unknown[]>;
}

interface DayMetric {
  date: string;
  metric: string;
  value: number;
  breakdown?: Record<string, number>;
}

function formatK(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(0)}K`;
  return `${n}`;
}

function PieTooltip({ active, payload }: { active?: boolean; payload?: Array<{ name: string; value: number; payload: { percent: number } }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0];
  return (
    <div style={{
      background: "rgba(255,255,255,0.97)", backdropFilter: "blur(12px)",
      border: "1px solid rgba(0,0,0,0.08)", borderRadius: "10px",
      padding: "8px 12px", fontSize: "11px",
      boxShadow: "0 4px 12px rgba(0,0,0,0.06)",
    }}>
      <div style={{ fontWeight: 700, color: "#1F2937", marginBottom: 2 }}>{d.name}</div>
      <div style={{ color: "#6B7280" }}>{formatK(d.value)} tokens ({Math.round(d.payload.percent)}%)</div>
    </div>
  );
}

export function TokenPieChart({ goals, goalMetrics }: Props) {
  const { locale } = useI18n();
  const [view, setView] = useState<"day" | "week">("day");

  const siMetrics = (goalMetrics["self_improvement"] || []) as DayMetric[];

  const tokenEntries = siMetrics.filter((m) => m.metric === "daily_tokens");
  if (tokenEntries.length === 0) return null;

  const latest = tokenEntries[tokenEntries.length - 1];

  let pieData: { name: string; value: number; percent: number }[] = [];
  let totalTokens = 0;
  let label = "";

  if (view === "day") {
    const bd = latest?.breakdown;
    if (bd && typeof bd === "object") {
      totalTokens = Object.values(bd).reduce((s, v) => s + (v as number), 0);
      pieData = Object.entries(bd)
        .sort(([, a], [, b]) => (b as number) - (a as number))
        .map(([name, value]) => ({
          name,
          value: value as number,
          percent: totalTokens > 0 ? ((value as number) / totalTokens) * 100 : 0,
        }));
    }
    label = locale === "zh" ? "今日模型消耗" : "Today's Model Usage";
  } else {
    const weekModels: Record<string, number> = {};
    const last7 = tokenEntries.slice(-7);
    for (const entry of last7) {
      if (entry.breakdown && typeof entry.breakdown === "object") {
        for (const [model, tokens] of Object.entries(entry.breakdown)) {
          weekModels[model] = (weekModels[model] || 0) + (tokens as number);
        }
      }
    }
    totalTokens = Object.values(weekModels).reduce((s, v) => s + v, 0);
    pieData = Object.entries(weekModels)
      .sort(([, a], [, b]) => b - a)
      .map(([name, value]) => ({
        name,
        value,
        percent: totalTokens > 0 ? (value / totalTokens) * 100 : 0,
      }));
    label = locale === "zh" ? "本周模型消耗" : "Weekly Model Usage";
  }

  if (pieData.length === 0 || totalTokens === 0) return null;

  return (
    <motion.div
      className="glass-card p-4"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, delay: 0.2 }}
    >
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
          {label}
        </h3>
        <div className="flex gap-1">
          {(["day", "week"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`text-[10px] px-2 py-0.5 rounded-full transition-colors cursor-pointer ${
                view === v
                  ? "bg-blue-100 text-blue-700 font-semibold"
                  : "bg-gray-50 text-gray-400 hover:bg-gray-100"
              }`}
            >
              {v === "day" ? (locale === "zh" ? "日" : "Day") : (locale === "zh" ? "周" : "Week")}
            </button>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-4">
        {/* Pie */}
        <div className="w-[120px] h-[120px] shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={pieData}
                cx="50%"
                cy="50%"
                innerRadius={30}
                outerRadius={52}
                paddingAngle={2}
                dataKey="value"
                animationDuration={600}
              >
                {pieData.map((_, i) => (
                  <Cell key={i} fill={COLORS[i % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip content={<PieTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        </div>

        {/* Legend + total */}
        <div className="flex-1 min-w-0">
          <div className="text-lg font-bold text-gray-800 mb-1">
            {formatK(totalTokens)}
            <span className="text-[10px] text-gray-400 ml-1 font-normal">tokens</span>
          </div>
          <div className="space-y-1">
            {pieData.map((d, i) => (
              <div key={d.name} className="flex items-center gap-2">
                <div
                  className="w-2.5 h-2.5 rounded-sm shrink-0"
                  style={{ backgroundColor: COLORS[i % COLORS.length] }}
                />
                <span className="text-[11px] text-gray-600 truncate flex-1">{d.name}</span>
                <span className="text-[11px] font-semibold text-gray-500 shrink-0">
                  {formatK(d.value)}
                </span>
                <span className="text-[10px] text-gray-400 w-8 text-right shrink-0">
                  {Math.round(d.percent)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
