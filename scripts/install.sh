#!/bin/bash
# Claude Code 语音输入触发器 - 安装脚本

set -e

echo "🚀 开始安装 Claude Code 语音输入触发器..."
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# 检查 Python 版本
echo "📋 检查 Python 版本..."
if ! command -v python3 &> /dev/null; then
    echo "❌ 未找到 Python 3，请先安装 Python 3.10+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo "✅ Python 版本: $PYTHON_VERSION"
echo ""

# 检查 Homebrew
echo "📋 检查 Homebrew..."
if ! command -v brew &> /dev/null; then
    echo "⚠️  未找到 Homebrew，正在安装..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo "✅ Homebrew 已安装"
fi
echo ""

# 安装 PortAudio (pyaudio 依赖)
echo "📦 安装 PortAudio..."
if ! brew list portaudio &> /dev/null; then
    brew install portaudio
else
    echo "✅ PortAudio 已安装"
fi
echo ""

# 创建虚拟环境
echo "🐍 创建 Python 虚拟环境..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✅ 虚拟环境创建成功"
else
    echo "✅ 虚拟环境已存在"
fi
echo ""

# 激活虚拟环境并安装依赖
echo "📦 安装 Python 依赖..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo "✅ 依赖安装完成"
echo ""

# 创建快捷命令
echo "🔗 创建快捷命令..."
SHORTCUT_PATH="/usr/local/bin/voice-input"

# 创建临时脚本文件
TEMP_SCRIPT=$(mktemp)
cat > "$TEMP_SCRIPT" << EOF
#!/bin/bash
# Claude Code 语音输入快捷命令
cd "$PROJECT_ROOT"
source venv/bin/activate
python3 voice_input.py "\$@"
EOF

# 使用 sudo 安装到系统目录
echo "需要管理员权限来安装全局命令..."
if sudo cp "$TEMP_SCRIPT" "$SHORTCUT_PATH" && sudo chmod +x "$SHORTCUT_PATH"; then
    echo "✅ 快捷命令创建成功: voice-input"
    rm "$TEMP_SCRIPT"
else
    echo "⚠️  无法创建全局命令，将使用本地命令"
    echo "   你可以运行: cd $PROJECT_ROOT && source venv/bin/activate && python3 voice_input.py"
    rm "$TEMP_SCRIPT"
fi
echo ""

# 测试安装
echo "🧪 测试安装..."
if python3 -c "import pyaudio, webrtcvad, pynput, requests" 2>/dev/null; then
    echo "✅ 所有依赖导入成功"
else
    echo "❌ 依赖导入失败，请检查安装"
    exit 1
fi
echo ""

# 检查 Whisper 服务
echo "🔍 检查 Whisper 服务..."
if curl -s http://localhost:8765/health > /dev/null 2>&1; then
    echo "✅ Whisper 服务运行正常"
else
    echo "⚠️  Whisper 服务未运行"
    echo "   请运行: whisper-service start"
fi
echo ""

# 完成
echo "🎉 安装完成！"
echo ""
echo "📖 使用方法："
echo "   1. 确保 Whisper 服务已启动: whisper-service start"
echo "   2. 运行: voice-input"
echo "   3. 或配置快捷键触发（见 README.md）"
echo ""
echo "⚙️  配置文件: $PROJECT_ROOT/config.yaml"
echo "📝 使用文档: $PROJECT_ROOT/README.md"
echo ""
