#!/bin/bash

# AI新闻网站启动脚本
# 作者: AI News Web Team
# 版本: 1.0

echo "=========================================="
echo "    AI新闻网站启动脚本"
echo "=========================================="

echo "🚀 启动AI新闻Web应用..."

# 检查Python是否安装
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 未安装，请先安装Python3"
    exit 1
fi

echo "✅ Python3 已安装: $(python3 --version)"

# 检查虚拟环境
if [ ! -d "ai_news_env" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv ai_news_env
fi

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
source ai_news_env/bin/activate

# 升级pip
echo "⬆️ 升级pip..."
pip install --upgrade pip

# 安装依赖
echo "📚 安装项目依赖..."
pip install -r requirements.txt

# 检查.env文件
if [ ! -f ".env" ]; then
    echo "📝 创建默认.env配置文件..."
    cat > .env << EOF
# 博查AI配置（请在此填写你的密钥）
BOCHA_API_KEY=
# 可选：接口切换（web-search 或 ai-search）
BOCHA_API_URL=https://api.bochaai.com/v1/web-search

# 火山引擎（可选，用于AI二次加工）
VOLCENGINE_API_KEY=
VOLCENGINE_ENDPOINT_ID=

# OpenAI配置（可选，用于AI二次加工）
OPENAI_API_KEY=
OPENAI_ORG_ID=
OPENAI_PROJECT_ID=
OPENAI_MODEL=gpt-3.5-turbo

# Flask配置
FLASK_ENV=development
FLASK_DEBUG=1
EOF
    echo "✅ 已创建.env文件，请根据需要配置 BOCHA/VOLCENGINE/OPENAI 等密钥"
fi

# 检查端口是否被占用
PORT=5000
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null ; then
    echo "⚠️ 端口 $PORT 已被占用，尝试停止现有进程..."
    pkill -f "python.*app.py" || true
    sleep 2
fi

# 启动应用
echo "🌟 启动Flask应用..."
echo "📱 应用将在 http://localhost:$PORT 运行"
echo "🔄 按 Ctrl+C 停止应用"
echo ""

python3 app.py

# 如果应用异常退出
echo ""
echo "❌ 应用已停止运行"
echo "💡 提示: 按 Ctrl+C 可以正常停止应用" 