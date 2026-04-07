#!/bin/bash
# ============================================================
# QuantifyU — 一键环境安装脚本
# 在终端中运行: bash ~/Desktop/Trade/quantifyu/setup.sh
# ============================================================

set -e
echo ""
echo "🚀 QuantifyU 环境安装开始..."
echo "================================"

# ---- 1. Homebrew ----
if ! command -v brew &>/dev/null; then
    echo ""
    echo "📦 [1/7] 安装 Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    # 添加到 PATH (Apple Silicon Mac)
    if [[ -f /opt/homebrew/bin/brew ]]; then
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
else
    echo "✅ [1/7] Homebrew 已安装"
fi

# ---- 2. Node.js ----
if ! command -v node &>/dev/null; then
    echo ""
    echo "📦 [2/7] 安装 Node.js 20..."
    brew install node@20
    brew link node@20 --force --overwrite 2>/dev/null || true
else
    echo "✅ [2/7] Node.js 已安装: $(node --version)"
fi

# ---- 3. Python 3.11 ----
if ! python3 --version 2>&1 | grep -q "3.1[1-9]"; then
    echo ""
    echo "📦 [3/7] 安装 Python 3.11..."
    brew install python@3.11
else
    echo "✅ [3/7] Python 已安装: $(python3 --version)"
fi

# ---- 4. 全局 CLI 工具 ----
echo ""
echo "📦 [4/7] 安装 Expo CLI + EAS CLI..."

# 修复 npm 全局目录权限（避免 EACCES）
NPM_GLOBAL="$HOME/.npm-global"
mkdir -p "$NPM_GLOBAL"
npm config set prefix "$NPM_GLOBAL"
# 添加到 PATH
if ! grep -q 'npm-global' ~/.zprofile 2>/dev/null; then
    echo 'export PATH="$HOME/.npm-global/bin:$PATH"' >> ~/.zprofile
fi
export PATH="$HOME/.npm-global/bin:$PATH"

npm install -g expo-cli eas-cli

# ---- 5. 后端 Python 依赖 ----
echo ""
echo "📦 [5/7] 安装后端 Python 依赖..."
cd ~/Desktop/Trade/quantifyu/services/api

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

# ---- 6. 前端 npm 依赖 ----
echo ""
echo "📦 [6/7] 安装前端 npm 依赖..."
cd ~/Desktop/Trade/quantifyu/apps/mobile
npm install

# ---- 7. 配置 .env 文件 ----
echo ""
echo "📦 [7/7] 生成 .env 配置文件..."

# 后端 .env
cd ~/Desktop/Trade/quantifyu/services/api
if [ ! -f ".env" ]; then
    MASTER_KEY=$(python3 -c "import base64,os;print(base64.b64encode(os.urandom(32)).decode())")
    cat > .env << ENVEOF
# QuantifyU Backend — 自动生成
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY
SUPABASE_JWT_SECRET=YOUR_JWT_SECRET

API_ENV=development
API_CORS_ORIGINS=http://localhost:8081,http://localhost:19006,http://localhost:8000

ENCRYPTION_MASTER_KEY=${MASTER_KEY}
ENCRYPTION_KEY_VERSION=1

MODEL_DEVICE=cpu
VIT_FBP_MODEL_PATH=./app/ai/models/vit_fbp.pth
ENVEOF
    echo "  ✅ 后端 .env 已生成（加密密钥已自动生成）"
    echo "  ⚠️  请编辑 services/api/.env 填入 Supabase 凭证"
else
    echo "  ✅ 后端 .env 已存在"
fi

# 前端 .env
cd ~/Desktop/Trade/quantifyu/apps/mobile
if [ ! -f ".env" ]; then
    cat > .env << ENVEOF
EXPO_PUBLIC_API_URL=http://localhost:8000
EXPO_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=YOUR_ANON_KEY
ENVEOF
    echo "  ✅ 前端 .env 已生成"
    echo "  ⚠️  请编辑 apps/mobile/.env 填入 Supabase 凭证"
else
    echo "  ✅ 前端 .env 已存在"
fi

# ---- 完成 ----
echo ""
echo "================================"
echo "🎉 QuantifyU 环境安装完成！"
echo "================================"
echo ""
echo "📋 下一步："
echo ""
echo "  1. 创建 Supabase 项目:"
echo "     https://supabase.com/dashboard → New Project"
echo ""
echo "  2. 填入 Supabase 凭证:"
echo "     vim ~/Desktop/Trade/quantifyu/services/api/.env"
echo "     vim ~/Desktop/Trade/quantifyu/apps/mobile/.env"
echo ""
echo "  3. 运行数据库迁移:"
echo "     在 Supabase SQL Editor 中运行:"
echo "     - quantifyu_schema.sql"
echo "     - supabase/migrations/002_privacy_hardening.sql"
echo ""
echo "  4. 启动后端:"
echo "     cd ~/Desktop/Trade/quantifyu/services/api"
echo "     source .venv/bin/activate"
echo "     uvicorn app.main:app --reload --port 8000"
echo ""
echo "  5. 启动前端 (新终端窗口):"
echo "     cd ~/Desktop/Trade/quantifyu/apps/mobile"
echo "     npx expo start"
echo ""
echo "  6. 运行测试:"
echo "     cd ~/Desktop/Trade/quantifyu/services/api"
echo "     source .venv/bin/activate"
echo "     python3 -m pytest tests/ -v -s"
echo ""
