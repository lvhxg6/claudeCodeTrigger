# Claude Code 语音输入触发器

通过语音输入文本到 Claude Code，完全本地化、无侵入、高效率。

## ✨ 特性

- **🎙️ 智能录音**：VAD 静音检测，说完自动停止
- **🧠 本地转录**：复用你的 Whisper 服务，无需重复加载模型
- **⌨️ 自动输入**：模拟键盘输入，对 Claude Code 完全透明
- **🚀 快捷触发**：支持全局快捷键，随时随地使用
- **🔒 隐私保护**：完全本地运行，音频不上传
- **🔊 声音反馈**：三个关键时刻播放提示音，清晰知道录音状态
- **✅ 手动确认**：只输入文本不自动提交，让你检查后再按回车

## 📋 快速参考

### 常用配置速查

| 配置项 | 默认值 | 说明 | 修改建议 |
|--------|--------|------|----------|
| `WHISPER_LANGUAGE` | `"zh"` | 识别语言 | 中文用 `"zh"`，英文用 `"en"` |
| `VAD_MODE` | `3` | 语音检测严格度 | 嘈杂环境用 `3`，安静环境可用 `2` |
| `SILENCE_THRESHOLD` | `1.5` | 静音多久停止（秒） | 说话慢用 `2.0`，说话快用 `1.0` |
| `AUTO_SUBMIT` | `False` | 是否自动按回车 | 建议保持 `False`，手动确认更安全 |
| `ENABLE_SOUND` | `True` | 是否启用提示音 | 不需要提示音可改为 `False` |
| `TYPING_DELAY` | `0.01` | 输入延迟（秒） | 输入太快出错可改为 `0.02` |

### 声音文件速查

| 声音 | 文件路径 | 特点 |
|------|----------|------|
| Tink | `/System/Library/Sounds/Tink.aiff` | 清脆的"叮"声，推荐用于开始/结束 |
| Pop | `/System/Library/Sounds/Pop.aiff` | 爆破声，推荐用于检测到语音 |
| Ping | `/System/Library/Sounds/Ping.aiff` | 乒乓声，轻快 |
| Hero | `/System/Library/Sounds/Hero.aiff` | 英雄音效，有气势 |
| Glass | `/System/Library/Sounds/Glass.aiff` | 玻璃碎裂声，明显 |

### 常见问题速查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 未检测到语音 | VAD 太严格 | 降低 `VAD_MODE` 到 `2` 或 `1` |
| 录音时间太长 | 环境噪音大 | 提高 `VAD_MODE` 到 `3`，或减少 `SILENCE_THRESHOLD` |
| 识别不准确 | 语言设置错误 | 检查 `WHISPER_LANGUAGE` 是否正确 |
| 输入太快出错 | 延迟太短 | 增加 `TYPING_DELAY` 到 `0.02` |
| 不想自动提交 | `AUTO_SUBMIT = True` | 改为 `False`（已默认关闭） |

## 🎯 工作原理

```
快捷键触发
   ↓
🎙️ 开始录音 (播放提示音)
   ↓
🗣️ 检测到语音 (播放提示音)
   ↓
录音 + VAD 静音检测
   ↓
🔇 静音 1.5 秒，停止录音 (播放提示音)
   ↓
调用 Whisper API (http://localhost:8765/v1)
   ↓
获取转录文本
   ↓
验证文本是否有效（非空、非纯空白）
   ↓
模拟键盘输入 (pynput)
   ↓
✅ 完成（不自动按回车，让你检查后手动提交）
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
1. 🎙️ 听到"叮"声，看到 "开始录音，请说话..." 提示
2. 🗣️ 开始说话，听到"啵"声表示检测到语音
3. 🔇 说完后保持安静 1.5 秒，听到"叮"声表示录音结束
4. 🧠 系统自动转录
5. ⌨️ 文本自动输入到当前应用
6. ✅ **检查识别结果，手动按回车提交**

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

### 配置文件方式（推荐）

从 v2.0.0 开始，支持通过 `config.yaml` 配置文件进行配置。编辑 `config.yaml`：

```yaml
# STT 引擎配置
stt:
  engine: "whisper"  # 可选: "whisper" 或 "funasr"
  streaming: false   # 流式模式（仅 FunASR 支持）

# Whisper 配置
whisper:
  api_url: "http://localhost:8765/v1/audio/transcriptions"
  language: "zh"  # zh=中文, en=英文, null=自动检测

# FunASR 配置（可选）
funasr:
  api_url: "http://localhost:10095/v1/audio/transcriptions"
  ws_url: "ws://localhost:10095/ws/transcribe"

# 音频录制配置
audio:
  sample_rate: 16000
  channels: 1
  chunk_duration_ms: 30
  padding_duration_ms: 300

# VAD 配置
vad:
  mode: 3  # 0-3，3 最严格
  silence_threshold: 1.5
  min_recording_seconds: 0.5
  max_recording_seconds: 60

# 键盘输入配置
keyboard:
  typing_delay: 0.01
  auto_submit: false

# 声音提示配置
sound:
  enabled: true
  start: "/System/Library/Sounds/Tink.aiff"
  detected: "/System/Library/Sounds/Pop.aiff"
  end: "/System/Library/Sounds/Tink.aiff"
```

### 代码配置方式（兼容旧版本）

也可以直接编辑 `voice_input.py` 中的 `Config` 类：

```python
class Config:
    # Whisper 服务配置
    WHISPER_API_URL = "http://localhost:8765/v1/audio/transcriptions"
    WHISPER_LANGUAGE = "zh"  # 语言：zh=中文, en=英文, auto=自动检测

    # 音频录制配置
    SAMPLE_RATE = 16000  # 采样率（Whisper 推荐 16kHz）
    CHANNELS = 1  # 声道数（1=单声道，2=立体声）
    CHUNK_DURATION_MS = 30  # 每个音频块时长（毫秒）
    PADDING_DURATION_MS = 300  # 静音前后填充时长（毫秒）

    # VAD 配置
    VAD_MODE = 3  # 0-3，数字越大越严格
                  # 0: 最宽松（容易误触发，但不会漏掉语音）
                  # 1: 宽松
                  # 2: 适中
                  # 3: 最严格（推荐，减少误触发）

    # 录音控制
    MAX_RECORDING_SECONDS = 60  # 最长录音时间（秒）
    SILENCE_THRESHOLD = 1.5  # 连续静音多少秒后停止录音
    MIN_RECORDING_SECONDS = 0.5  # 最短录音时间（秒，避免误触发）

    # 键盘输入配置
    TYPING_DELAY = 0.01  # 每个字符输入延迟（秒）
    AUTO_SUBMIT = False  # 是否自动按 Enter
                         # False: 只输入文本，让你检查后手动按回车
                         # True: 自动按回车提交

    # 声音提示配置
    ENABLE_SOUND = True  # 是否启用声音提示
    SOUND_START = "/System/Library/Sounds/Tink.aiff"      # 开始录音提示音
    SOUND_DETECTED = "/System/Library/Sounds/Pop.aiff"    # 检测到语音提示音
    SOUND_END = "/System/Library/Sounds/Tink.aiff"        # 结束录音提示音
```

### 🚀 FunASR 流式识别（新功能）

支持使用 FunASR 进行流式语音识别，实现边说边出文字的效果：

**特点**：
- **实时性更强**：延迟 200-500ms（vs Whisper 的 2.5-3.5s）
- **边说边出**：文字实时显示，无需等待说完
- **本地部署**：完全免费，无需联网

**使用方法**：

1. 安装 FunASR 服务（参见 [claudeCodeFunasr](../claudeCodeFunasr)）
2. 启动 FunASR 服务：`funasr-service start`
3. 修改 `config.yaml`：
   ```yaml
   stt:
     engine: "funasr"
     streaming: true  # 启用流式模式
   ```
4. 运行 `voice-input`，体验实时识别

**对比**：

| 特性 | Whisper | FunASR（非流式） | FunASR（流式） |
|------|---------|------------------|----------------|
| 延迟 | 2.5-3.5s | 1-2s | 0.2-0.5s |
| 实时性 | ❌ | ❌ | ✅ |
| 中文识别 | ✅ | ✅ | ✅ |
| 英文识别 | ✅ | ✅ | ✅ |
| 本地部署 | ✅ | ✅ | ✅ |

### 🔊 声音提示配置详解

系统在三个关键时刻播放提示音：

| 时机 | 配置项 | 默认声音 | 说明 |
|------|--------|----------|------|
| 🎙️ 开始录音 | `SOUND_START` | Tink.aiff | 按下快捷键后立即播放 |
| 🗣️ 检测到语音 | `SOUND_DETECTED` | Pop.aiff | VAD 检测到有效语音时播放 |
| 🔇 结束录音 | `SOUND_END` | Tink.aiff | 静音超过阈值，停止录音时播放 |

#### macOS 系统可用声音列表

```bash
# 查看所有系统声音
ls /System/Library/Sounds/

# 常用声音文件：
/System/Library/Sounds/Basso.aiff       # 低沉的"咚"声
/System/Library/Sounds/Blow.aiff        # 吹气声
/System/Library/Sounds/Bottle.aiff      # 瓶子声
/System/Library/Sounds/Frog.aiff        # 青蛙叫声
/System/Library/Sounds/Funk.aiff        # 放克音效
/System/Library/Sounds/Glass.aiff       # 玻璃碎裂声
/System/Library/Sounds/Hero.aiff        # 英雄音效
/System/Library/Sounds/Morse.aiff       # 摩斯电码声
/System/Library/Sounds/Ping.aiff        # 乒乓声
/System/Library/Sounds/Pop.aiff         # 爆破声（推荐）
/System/Library/Sounds/Purr.aiff        # 猫叫声
/System/Library/Sounds/Sosumi.aiff      # 经典 Mac 声音
/System/Library/Sounds/Submarine.aiff   # 潜水艇声
/System/Library/Sounds/Tink.aiff        # 清脆的"叮"声（推荐）
```

#### 试听声音

```bash
# 试听某个声音
afplay /System/Library/Sounds/Pop.aiff

# 试听所有声音
for sound in /System/Library/Sounds/*.aiff; do
    echo "Playing: $(basename $sound)"
    afplay "$sound"
    sleep 0.5
done
```

#### 自定义声音

你也可以使用自己的音频文件：

```python
# 使用自定义声音文件
SOUND_START = "/Users/你的用户名/Music/my_start_sound.aiff"
SOUND_DETECTED = "/Users/你的用户名/Music/my_detected_sound.mp3"
SOUND_END = "/Users/你的用户名/Music/my_end_sound.wav"
```

支持的格式：`.aiff`, `.wav`, `.mp3`, `.m4a` 等 macOS 支持的音频格式。

#### 关闭声音提示

如果不需要声音提示：

```python
ENABLE_SOUND = False  # 关闭所有声音提示
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

## 📝 更新日志

### v1.2.0 (2026-01-22)

**重要修复：FunASR 流式识别问题**

- 🐛 **修复识别不准确问题**
  - 问题：之前每个音频块都被包装成独立的 WAV 文件（含 44 字节头），导致音频数据损坏
  - 修复：现在直接发送原始 PCM 数据，音频数据完整连续
  - 效果：识别准确率从 ~60-70% 提升至 ~90%+

- 🐛 **修复 WebSocket 连接超时问题**
  - 问题：多次执行 `voice-input` 时出现 "timed out during opening handshake"
  - 原因：服务端推理阻塞、客户端超时太短、资源未清理
  - 修复：
    - 客户端超时从 0.1s 增加到 1.0s
    - 服务端每 10 块推理一次（vs 每块都推理）
    - 添加资源清理和异常处理

**性能优化：**

- ⚡ 推理频率降低 90%（每 10 块推理一次）
- ⚡ 移除不必要的 WAV 头，减少网络传输 ~5%
- ⚡ 添加缓冲区大小限制，防止内存溢出
- ⚡ 添加连接池管理，限制最大并发连接数

**技术改进：**

- 服务端现在从配置文件读取流式参数：
  ```yaml
  streaming:
    inference_batch_size: 10  # 推理批次大小
    max_buffer_size: 100      # 最大缓冲区大小
    max_connections: 10       # 最大连接数
  ```

### v1.1.0 (2026-01-21)

**新增功能：**
- ✅ 添加声音提示反馈系统
  - 开始录音时播放提示音
  - 检测到语音时播放提示音
  - 结束录音时播放提示音
  - 可自定义声音文件或关闭提示音

**改进：**
- ✅ 关闭自动回车功能（`AUTO_SUBMIT = False`）
  - 现在只输入文本，不自动提交
  - 让用户检查识别结果后手动按回车
  - 避免误识别导致执行错误命令

- ✅ 添加文本验证
  - 检查转录结果是否为空或仅包含空白字符
  - 如果没有有效文本，跳过输入并显示警告
  - 防止空内容被输入和提交

**修复：**
- 🐛 修复空文本输入 bug
  - 之前：即使没有识别到有效语音，也会按回车，导致终端执行空命令
  - 现在：验证文本有效性，无效文本不会输入

### v1.0.0 (2026-01-21)

**初始版本：**
- 🎙️ 智能录音 + VAD 静音检测
- 🧠 本地 Whisper 转录
- ⌨️ 键盘输入模拟
- 🚀 全局快捷键支持

## 📄 许可证

MIT License
