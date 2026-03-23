#!/usr/bin/env bash
# OA Auto-Collect — 一键采集 + 飞书推送
# 用于 Cron 自动执行或手动运行
#
# Usage:
#   bash scripts/oa-auto-collect.sh [--report] [--config path]
#
set -euo pipefail

OA_PROJECT="${OA_PROJECT:-/tmp/oa-test-project}"
CONFIG="${OA_PROJECT}/config.yaml"
SEND_REPORT=false

for arg in "$@"; do
    case "$arg" in
        --report) SEND_REPORT=true ;;
        --config=*) CONFIG="${arg#*=}" ;;
    esac
done

echo "━━━ OA Auto-Collect $(date '+%Y-%m-%d %H:%M') ━━━"
echo "Project: ${OA_PROJECT}"

# Step 1: Collect
echo ""
echo "📊 Running oa collect..."
cd "${OA_PROJECT}"
oa collect --config "${CONFIG}" 2>&1

# Step 2: Status
echo ""
echo "📋 Current status:"
oa status --config "${CONFIG}" 2>&1

# Step 3: Report (optional)
if [ "${SEND_REPORT}" = true ]; then
    echo ""
    echo "📤 Sending Feishu report..."
    oa report --config "${CONFIG}" 2>&1
fi

echo ""
echo "━━━ Done $(date '+%H:%M:%S') ━━━"
