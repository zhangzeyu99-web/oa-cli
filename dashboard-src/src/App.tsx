import { useState, useMemo } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useOAData } from "./hooks/useOAData";
import { SystemHealth } from "./components/SystemHealth";
import { MechanismView } from "./components/MechanismView";
import { I18nContext, t as _t, tMetric as _tM, tGoal as _tG, type Locale } from "./i18n";

type Tab = "system-health" | "mechanism";

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("system-health");
  const [locale, setLocale] = useState<Locale>("zh");
  const { goals, health, traces, cronRuns, teamHealth, goalMetrics, isLoading, error } = useOAData(30_000);

  const i18n = useMemo(() => ({
    locale,
    t: (k: string) => _t(k, locale),
    tMetric: (k: string) => _tM(k, locale),
    tGoal: (k: string) => _tG(k, locale),
    toggle: () => setLocale((l) => (l === "en" ? "zh" : "en")),
  }), [locale]);

  const tabLabels: Record<Tab, Record<Locale, string>> = {
    "system-health": { en: "System Health", zh: "系统健康" },
    "mechanism": { en: "Mechanism", zh: "运行机制" },
  };

  return (
    <I18nContext.Provider value={i18n}>
      <div className="min-h-screen">
        <div className="max-w-7xl mx-auto px-4 py-6">
          {/* Header */}
          <div className="flex items-center justify-between mb-6">
            <div>
              <h1 className="text-xl font-bold text-gray-900 tracking-tight">
                {i18n.t("OA Dashboard")}
              </h1>
              <p className="text-xs text-gray-400 mt-0.5">
                {i18n.t("Is our machine getting better?")}
              </p>
            </div>

            <div className="flex items-center gap-4">
              <nav className="flex gap-6">
                {(["system-health", "mechanism"] as Tab[]).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={`pb-1 text-sm transition-all ${
                      activeTab === tab ? "tab-active" : "tab-inactive"
                    }`}
                  >
                    {tabLabels[tab][locale]}
                  </button>
                ))}
              </nav>

              {/* Language Toggle */}
              <button
                onClick={i18n.toggle}
                className="flex items-center gap-1 px-2.5 py-1 rounded-full bg-gray-100 hover:bg-gray-200 transition-colors text-[11px] font-medium text-gray-500 cursor-pointer"
                title={locale === "zh" ? "Switch to English" : "切换中文"}
              >
                <span className="text-sm">{locale === "zh" ? "🇨🇳" : "🇺🇸"}</span>
                {locale === "zh" ? "中" : "EN"}
              </button>
            </div>
          </div>

          {/* Content */}
          <AnimatePresence mode="wait">
            {isLoading ? (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center justify-center py-32"
              >
                <div className="text-center space-y-4">
                  <motion.div
                    className="w-8 h-8 rounded-full border-2 border-gray-200 mx-auto"
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
                    style={{ borderTopColor: "#60A5FA" }}
                  />
                  <p className="text-[10px] text-gray-400 uppercase tracking-[0.3em] font-mono">
                    {i18n.t("Loading")}
                  </p>
                </div>
              </motion.div>
            ) : error && !goals.length ? (
              <motion.div
                key="error"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex items-center justify-center py-32"
              >
                <div className="glass-card p-8 max-w-md text-center space-y-3">
                  <p className="text-sm text-gray-600">{i18n.t("Connection Error")}</p>
                  <p className="text-xs text-gray-400 font-mono">{error}</p>
                  <p className="text-[10px] text-gray-400">
                    {i18n.t("Ensure the API server is running:")} <code>oa serve</code>
                  </p>
                </div>
              </motion.div>
            ) : (
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.3 }}
              >
                {activeTab === "system-health" ? (
                  <SystemHealth
                    goals={goals}
                    health={health}
                    goalMetrics={goalMetrics}
                    cronRuns={cronRuns}
                    teamHealth={teamHealth}
                  />
                ) : activeTab === "mechanism" ? (
                  <MechanismView
                    goals={goals}
                    traces={traces}
                    cronRuns={cronRuns}
                  />
                ) : null}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Footer */}
          <motion.div
            className="text-center py-4 mt-8"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.8 }}
          >
            <span className="text-[10px] text-gray-300 font-mono tracking-wider uppercase">
              {i18n.t("OA — Operational Analytics")}
            </span>
          </motion.div>
        </div>
      </div>
    </I18nContext.Provider>
  );
}
