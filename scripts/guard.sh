#!/bin/bash
# ============================================================
# Git 安全守卫
# 确保所有 AI 操作在 Git 项目内部运行
# 用法: source scripts/guard.sh
#       或在 .git/hooks/pre-commit 中调用
# ============================================================

set -euo pipefail

GUARD_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo '')"
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

fail() {
  echo -e "${RED}❌ 拒绝: $1${NC}" >&2
  exit 1
}

warn() {
  echo -e "${YELLOW}⚠️  警告: $1${NC}" >&2
}

ok() {
  echo -e "${GREEN}✅ $1${NC}"
}

# ============================================================
# 第一层: Git 仓库检查
# ============================================================
if [ -z "$GUARD_ROOT" ]; then
  fail "当前目录不是 Git 仓库。请在项目目录内运行。"
fi

CURRENT_DIR="$(pwd -P)"

# 确保在项目目录内
if [[ "$CURRENT_DIR" != "$GUARD_ROOT"* ]]; then
  fail "当前目录 ($CURRENT_DIR) 不在项目根目录 ($GUARD_ROOT) 内。"
fi

ok "Git 仓库检查通过 — 在项目目录内"

# ============================================================
# 第二层: 敏感文件检查
# ============================================================
STAGED_FILES=$(git diff --cached --name-only 2>/dev/null || echo "")

if [ -n "$STAGED_FILES" ]; then
  # 检查 .env / secret / credentials 文件
  SENSITIVE_FILES=$(echo "$STAGED_FILES" | grep -E '\.env$|\.env\.|secret|credentials|\.pem$|\.key$' || true)
  if [ -n "$SENSITIVE_FILES" ]; then
    fail "检测到敏感文件被暂存:\n$SENSITIVE_FILES\n\n这些文件不应提交到仓库。请用 git rm --cached 移除。"
  fi

  # 检查硬编码密钥（常见模式）
  HARDCODED_SECRETS=$(git diff --cached --unified=0 | grep -E '(api_key|apikey|secret_key|password|token)\s*=\s*["'"'"'][A-Za-z0-9_\-]{8,}' || true)
  if [ -n "$HARDCODED_SECRETS" ]; then
    warn "检测到可能的硬编码密钥，请检查:\n$HARDCODED_SECRETS"
  fi
fi

ok "敏感文件检查通过"

# ============================================================
# 第三层: 未提交变更提醒
# ============================================================
UNSTAGED=$(git status --porcelain 2>/dev/null || echo "")
UNSTAGED_COUNT=$(echo "$UNSTAGED" | grep -v '^$' | wc -l || echo 0)

if [ "$UNSTAGED_COUNT" -gt 0 ]; then
  warn "有 $UNSTAGED_COUNT 个文件存在未提交的变更。建议先 commit 或 stash 再让 AI 操作。"
  echo "$UNSTAGED" | head -10
fi

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  ✅ 安全检查全部通过${NC}"
echo -e "${GREEN}============================================${NC}"
