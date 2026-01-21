# Claude Code 语音输入触发器

通过语音输入文本到 Claude Code，完全本地化、无侵入、高效率。

## ✨ 特性

- **🎙️ 智能录音**：VAD 静音检测，说完自动停止
- **🧠 本地转录**：复用你的 Whisper 服务，无需重复加载模型
- **⌨️ 自动输入**：模拟键盘输入，对 Claude Code 完全透明
- **🚀 快捷触发**：支持全局快捷键，随时随地使用
- **🔒 隐私保护**：完全本地运行，音频不上传

## 🎯 工作原理

```
快捷键触发
   ↓
录音 (pyaudio + VAD)
   ↓
调用 Whisper API (http://localhost:8765/v1)
   ↓
获取转录文本
   ↓
模拟键盘输入 (pynput)
   ↓
自动按 Enter 提交
```

## 📦 安装

### 1. 运行安装脚本

```bash
cd /Users/liubu/hx/AI-SystemService/claudeCodeTrigger
./scripts/install.sh
```

安装脚本会自动：
- 检查 Python 版本
- 安装 PortAudio（pyaudio 依赖）
- 创建虚拟环境
- 安装 Python 依赖
- 创建快捷命令 `voice-input`

### 2. 确保 Whisper 服务运行

```bash
whisper-service start
```

## 🚀 使用方法

### 方式 1：命令行直接运行

```bash
voice-input
```

然后：
1. 看到 "🎙️ 开始录音，请说话..." 提示
2. 开始说话
3. 说完后保持安静 1.5 秒
4. 自动转录并输入到当前应用

### 方式 2：配置全局快捷键（推荐）

#### 使用 Raycast（推荐）

1. 安装 Raycast：https://www.raycast.com
2. 打开 Raycast → Create Script Command
3. 配置：
   - **Name**: Voice Input
   - **Command**: `voice-input`
   - **Mode**: Silent
   - **Shortcut**: `⌥⌘Space`（或你喜欢的快捷键）

#### 使用 Hammerspoon

1. 安装 Hammerspoon：`brew install hammerspoon`
2. 编辑 `~/.hammerspoon/init.lua`：

```lua
-- 语音输入快捷键
hs.hotkey.bind({"alt", "cmd"}, "space", function()
    hs.task.new("/usr/local/bin/voice-input", nil):start()
end)
```

3. 重新加载配置

## ⚙️ 配置说明

编辑 `voice_input.py` 中的 `Config` 类：

```python
class Config:
    # Whisper 服务配置
    WHISPER_API_URL = "http://localhost:8765/v1/audio/transcriptions"
    WHISPER_LANGUAGE = "zh"  # 语言：zh=中文, en=英文

    # VAD 配置
    VAD_MODE = 3  # 0-3，3 最严格（减少误触发）

    # 录音控制
    MAX_RECORDING_SECONDS = 60  # 最长录音时间
    SILENCE_THRESHOLD = 1.5  # 连续静音 1.5 秒后停止
    MIN_RECORDING_SECONDS = 0.5  # 最短录音时间

    # 键盘输入配置
    TYPING_DELAY = 0.01  # 每个字符输入延迟（秒）
    AUTO_SUBMIT = True  # 是否自动按 Enter
```

## 🔍 键盘输入模拟详解

### 使用的技术：pynput

`pynput` 是一个跨平台的 Python 库，用于控制和监控输入设备。

#### 工作原理

```python
from pynput.keyboard import Controller, Key

keyboard = Controller()

# 1. 逐字符输入
for char in "你好世界":
    keyboard.type(char)  # 模拟按键
    time.sleep(0.01)     # 短暂延迟，更自然

# 2. 按下特殊键
keyboard.press(Key.enter)    # 按下 Enter
keyboard.release(Key.enter)  # 释放 Enter
```

#### 为什么选择 pynput？

| 方案 | 优点 | 缺点 |
|------|------|------|
| **pynput** ✅ | 跨平台、稳定、支持中文 | - |
| AppleScript | macOS 原生 | 特殊字符处理复杂、速度慢 |
| pyautogui | 功能强大 | 依赖多、较重 |
| Quartz (PyObjC) | 底层 API | 仅 macOS、复杂 |

#### 中文输入处理

pynput 通过以下方式处理中文：

1. **Unicode 支持**：直接发送 Unicode 字符
2. **系统输入法**：利用 macOS 的输入系统
3. **逐字符输入**：确保每个字符正确输入

```python
# 示例：输入中文
keyboard.type("帮我分析这个代码")
# 等价于用户手动输入每个字符
```

## 🎬 使用场景

### 场景 1：代码审查

```
你：[按快捷键] "帮我审查这个函数的性能问题"
   ↓
Claude Code 收到：帮我审查这个函数的性能问题
```

### 场景 2：快速查询

```
你：[按快捷键] "这个错误是什么原因"
   ↓
Claude Code 收到：这个错误是什么原因
```

### 场景 3：长文本输入

```
你：[按快捷键] "我需要实现一个用户认证系统，包括登录、注册、密码重置功能"
   ↓
Claude Code 收到：我需要实现一个用户认证系统，包括登录、注册、密码重置功能
```

## 🔧 故障排查

### 1. 录音失败

**问题**：提示 "未检测到有效语音"

**解决**：
- 检查麦克风权限：系统设置 → 隐私与安全性 → 麦克风
- 降低 VAD 严格度：`VAD_MODE = 2`
- 减少最小录音时间：`MIN_RECORDING_SECONDS = 0.3`

### 2. 转录失败

**问题**：提示 "无法连接到 Whisper 服务"

**解决**：
```bash
# 检查服务状态
whisper-service status

# 启动服务
whisper-service start

# 测试 API
curl http://localhost:8765/health
```

### 3. 键盘输入失败

**问题**：文字没有输入到应用

**解决**：
- 检查辅助功能权限：系统设置 → 隐私与安全性 → 辅助功能
- 确保焦点在正确的输入框
- 增加输入延迟：`TYPING_DELAY = 0.02`

### 4. 中文输入乱码

**问题**：中文显示为乱码或问号

**解决**：
- 确保终端/应用支持 UTF-8
- 检查 Python 环境编码：
  ```bash
  python3 -c "import sys; print(sys.getdefaultencoding())"
  # 应该输出: utf-8
  ```

## 📊 性能指标

在 M4 Max + 128GB 配置下：

| 指标 | 数值 |
|------|------|
| 录音延迟 | < 100ms |
| 转录速度 | ~1-2 秒（取决于音频长度） |
| 输入速度 | ~100 字符/秒 |
| 内存占用 | ~50MB（不含 Whisper 服务） |

## 🆚 与 VoiceMode MCP 的区别

| 特性 | VoiceMode MCP | 本方案 |
|------|---------------|--------|
| 集成方式 | MCP 工具调用 | 键盘输入模拟 |
| 文字显示 | Tool Result（不可见） | 输入框可见 |
| 使用场景 | 语音对话 | 快速输入 |
| 灵活性 | 受 MCP 限制 | 完全自由 |
| 适用范围 | 仅 Claude Code | 任何应用 |

## 🎯 最佳实践

1. **快捷键选择**：避免与系统快捷键冲突，推荐 `⌥⌘Space`
2. **录音环境**：安静环境效果最佳，嘈杂环境可提高 `VAD_MODE`
3. **说话技巧**：清晰、匀速，避免长时间停顿
4. **结束录音**：说完后保持安静 1.5 秒即可自动停止
5. **焦点管理**：确保光标在输入框中再触发快捷键

## 📝 项目结构

```
claudeCodeTrigger/
├── voice_input.py          # 主程序
├── requirements.txt        # Python 依赖
├── README.md              # 本文档
├── scripts/
│   └── install.sh         # 安装脚本
└── logs/                  # 日志目录
```

## 🤝 与 claudeCodeWhisper 的关系

- **claudeCodeWhisper**：Whisper 服务端，提供转录 API
- **claudeCodeTrigger**：客户端，调用 API 并模拟输入

两者配合使用，互不影响。

## 📄 许可证

MIT License
