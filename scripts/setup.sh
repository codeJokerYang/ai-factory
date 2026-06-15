#!/bin/bash
# ============================================================
# 一人公司工作流 — 一键初始化脚本
# 用法: bash scripts/setup.sh
# ============================================================

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  一人公司 AI 工作流 — 初始化${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

# 0. 确认
echo "这个脚本将为你的项目配置 AI 工作流。"
echo "包括: Git Hooks, MCP 配置, Wiki 模板, CI 防线"
echo ""
read -p "继续? (y/n): " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
  echo "已取消。"
  exit 0
fi

PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo '')"
if [ -z "$PROJECT_ROOT" ]; then
  echo "❌ 当前目录不是 Git 仓库。请先 git init。"
  exit 1
fi

cd "$PROJECT_ROOT"

# 1. 安装 Git Hooks
echo ""
echo "→ 配置 Git Hooks..."
cp scripts/guard.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit

# pre-push hook
cat > .git/hooks/pre-push << 'HOOK_EOF'
#!/bin/bash
echo "🔒 Git 防线: 推送前检查..."

# 测试
if [ -f package.json ] && grep -q '"test"' package.json; then
  echo "→ 运行测试..."
  npm test || { echo "❌ 测试未通过，禁止 push"; exit 1; }
fi

# Lint
if [ -f package.json ] && grep -q '"lint"' package.json; then
  echo "→ 运行 Lint..."
  npm run lint || { echo "❌ Lint 未通过，禁止 push"; exit 1; }
fi

echo "✅ 检查通过。"
HOOK_EOF
chmod +x .git/hooks/pre-push

echo -e "${GREEN}✅ Git Hooks 已配置${NC}"

# 2. 创建 .gitignore（如果不存在）
if [ ! -f .gitignore ]; then
  cat > .gitignore << 'IGNORE_EOF'
# 依赖
node_modules/
.pnp
.pnp.js

# 构建
dist/
build/
.next/
out/

# 环境变量
.env
.env.local
.env.*.local

# IDE
.vscode/
.idea/
*.swp
*.swo

# 系统
.DS_Store
Thumbs.db

# 日志
*.log
npm-debug.log*

# Claude Code
.claude/transcripts/
IGNORE_EOF
  echo -e "${GREEN}✅ .gitignore 已创建${NC}"
fi

# 3. 验证目录结构
echo ""
echo "→ 验证目录结构..."
DIRS=("wiki/decisions" "wiki/specs" "wiki/conventions" "wiki/runbooks" "scripts" ".github/workflows")
for dir in "${DIRS[@]}"; do
  if [ -d "$dir" ]; then
    echo -e "${GREEN}  ✅ $dir${NC}"
  else
    mkdir -p "$dir"
    echo -e "${YELLOW}  📁 已创建: $dir${NC}"
  fi
done

# 4. MCP 配置提醒
echo ""
echo -e "${YELLOW}⚠️  请手动配置以下内容:${NC}"
echo ""
echo "  1. 编辑 .claude/mcp.json:"
echo "     - 将 filesystem 的路径改为你的实际项目路径"
echo "     - 配置 GITHUB_TOKEN 环境变量"
echo "     - 配置 DATABASE_URL 环境变量（如使用数据库）"
echo ""
echo "  2. 编辑 CLAUDE.md:"
echo "     - 填入项目名称、描述、技术栈"
echo ""
echo "  3. 编辑 wiki/ 下的模板:"
echo "     - 填入实际的架构决策和功能规格"
echo ""

echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}  ✅ 初始化完成!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""
echo "下一步:"
echo "  1. 编辑 CLAUDE.md — 填入项目信息"
echo "  2. 编辑 .claude/mcp.json — 配置实际路径"
echo "  3. 用 Claude Code 写第一个 spec:"
echo "     @claude \"根据 wiki/specs/template.md 模板，写第一个功能规格\""
echo "  4. 开始开发!"
