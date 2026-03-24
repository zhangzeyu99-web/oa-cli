import { motion } from "framer-motion";
import type { GoalSummary } from "../types";
import { useI18n } from "../i18n";

interface Props {
  goals: GoalSummary[];
}

function statusIcon(value: number | null, healthy: number, warning: number, invert?: boolean): string {
  if (value === null) return "gray";
  if (invert) {
    return value <= healthy ? "#34D399" : value <= warning ? "#FBBF24" : "#F87171";
  }
  return value >= healthy ? "#34D399" : value >= warning ? "#FBBF24" : "#F87171";
}

export function HealStrip({ goals }: Props) {
  const { t, tMetric, locale } = useI18n();
  const si = goals.find((g) => g.id === "self_improvement");
  if (!si) return null;

  const m = si.metrics;
  const score = m.heal_score?.value;
  const tokens = m.daily_tokens?.value;
  const dups = m.memory_duplicates?.value;
  const longs = m.long_sessions?.value;
  const missing = m.skills_missing_doc?.value;

  const items: { label: string; value: string; color: string }[] = [];

  if (score !== null && score !== undefined) {
    items.push({
      label: locale === "zh" ? "改进得分" : "Heal Score",
      value: `${Math.round(score)}%`,
      color: statusIcon(score, 80, 50),
    });
  }
  if (tokens !== null && tokens !== undefined) {
    items.push({
      label: locale === "zh" ? "今日 Tokens" : "Tokens",
      value: tokens > 1000 ? `${Math.round(tokens / 1000)}K` : `${Math.round(tokens)}`,
      color: statusIcon(tokens, 200000, 500000, true),
    });
  }
  if (dups !== null && dups !== undefined) {
    items.push({
      label: locale === "zh" ? "记忆重复" : "Duplicates",
      value: `${Math.round(dups)}`,
      color: statusIcon(dups, 10, 50, true),
    });
  }
  if (longs !== null && longs !== undefined) {
    items.push({
      label: locale === "zh" ? "过长对话" : "Long Sessions",
      value: `${Math.round(longs)}`,
      color: statusIcon(longs, 2, 5, true),
    });
  }
  if (missing !== null && missing !== undefined) {
    items.push({
      label: locale === "zh" ? "技能缺失" : "Missing Docs",
      value: `${Math.round(missing)}`,
      color: statusIcon(missing, 1, 3, true),
    });
  }

  if (items.length === 0) return null;

  return (
    <motion.div
      className="glass-card px-4 py-2 flex items-center justify-between gap-4 text-xs"
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <span className="text-[10px] font-semibold text-gray-400 uppercase tracking-wider shrink-0">
        {locale === "zh" ? "自动改进" : "Self-Improvement"}
      </span>
      <div className="flex items-center gap-4 overflow-x-auto">
        {items.map((item) => (
          <div key={item.label} className="flex items-center gap-1.5 shrink-0">
            <div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: item.color }}
            />
            <span className="text-[11px] text-gray-500">{item.label}</span>
            <span className="text-[11px] font-bold" style={{ color: item.color }}>
              {item.value}
            </span>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
