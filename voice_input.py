#!/usr/bin/env python3
"""
Claude Code 语音输入触发器

通过语音输入文本到 Claude Code，支持：
- 本地录音 + VAD 静音检测
- 调用本地 Whisper 服务进行转录
- 自动模拟键盘输入到当前应用
- 自动按 Enter 提交
"""

import os
import sys
import wave
import time
import json
import tempfile
import logging
import subprocess
from pathlib import Path
from typing import Optional

import pyaudio
import webrtcvad
import requests
from pynput.keyboard import Controller, Key

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.absolute()
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# ===========================================
# 配置参数
# ===========================================

class Config:
    """配置类"""

    # Whisper 服务配置
    WHISPER_API_URL = "http://localhost:8765/v1/audio/transcriptions"
    WHISPER_LANGUAGE = "zh"  # 中文

    # 音频录制配置
    SAMPLE_RATE = 16000  # Whisper 推荐 16kHz
    CHANNELS = 1  # 单声道
    CHUNK_DURATION_MS = 30  # 每个音频块 30ms
    PADDING_DURATION_MS = 300  # 静音前后填充 300ms

    # VAD 配置
    VAD_MODE = 3  # 0-3，3 最严格（减少误触发）

    # 录音控制
    MAX_RECORDING_SECONDS = 60  # 最长录音时间
    SILENCE_THRESHOLD = 1.5  # 连续静音 1.5 秒后停止
    MIN_RECORDING_SECONDS = 0.5  # 最短录音时间

    # 键盘输入配置
    TYPING_DELAY = 0.01  # 每个字符输入延迟（秒）
    AUTO_SUBMIT = True  # 是否自动按 Enter

    # 声音提示配置
    ENABLE_SOUND = True  # 是否启用声音提示
    SOUND_START = "/System/Library/Sounds/Tink.aiff"  # 开始录音提示音
    SOUND_DETECTED = "/System/Library/Sounds/Pop.aiff"  # 检测到语音提示音
    SOUND_END = "/System/Library/Sounds/Tink.aiff"  # 结束录音提示音


# ===========================================
# 工具函数
# ===========================================

def play_sound(sound_path: str, config: Config):
    """播放系统提示音"""
    if not config.ENABLE_SOUND:
        return
    try:
        subprocess.Popen(
            ['afplay', sound_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except Exception as e:
        logger.debug(f"播放提示音失败: {e}")


# ===========================================
# 音频录制 + VAD
# ===========================================

class VoiceRecorder:
    """语音录制器（带 VAD）"""

    def __init__(self, config: Config):
        self.config = config
        self.vad = webrtcvad.Vad(config.VAD_MODE)
        self.audio = pyaudio.PyAudio()

        # 计算参数
        self.chunk_size = int(config.SAMPLE_RATE * config.CHUNK_DURATION_MS / 1000)
        self.padding_chunks = int(config.PADDING_DURATION_MS / config.CHUNK_DURATION_MS)

    def record(self) -> Optional[bytes]:
        """
        录音直到检测到静音

        Returns:
            bytes: 音频数据（WAV 格式），如果录音失败返回 None
        """
        logger.info("🎙️  开始录音，请说话...")
        play_sound(self.config.SOUND_START, self.config)

        # 打开音频流
        stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=self.config.CHANNELS,
            rate=self.config.SAMPLE_RATE,
            input=True,
            frames_per_buffer=self.chunk_size
        )

        frames = []
        voiced_frames = []
        num_padding_chunks = 0
        ring_buffer = []
        triggered = False

        start_time = time.time()
        silence_start = None

        try:
            while True:
                # 检查是否超时
                elapsed = time.time() - start_time
                if elapsed > self.config.MAX_RECORDING_SECONDS:
                    logger.warning("⏱️  录音超时，自动停止")
                    break

                # 读取音频块
                chunk = stream.read(self.chunk_size, exception_on_overflow=False)
                frames.append(chunk)

                # VAD 检测
                is_speech = self.vad.is_speech(chunk, self.config.SAMPLE_RATE)

                if not triggered:
                    # 等待语音开始
                    ring_buffer.append((chunk, is_speech))
                    if len(ring_buffer) > self.padding_chunks:
                        ring_buffer.pop(0)

                    num_voiced = sum(1 for _, speech in ring_buffer if speech)
                    if num_voiced > 0.5 * len(ring_buffer):
                        triggered = True
                        logger.info("🗣️  检测到语音，开始录制...")
                        play_sound(self.config.SOUND_DETECTED, self.config)
                        # 添加缓冲区内容
                        for buf_chunk, _ in ring_buffer:
                            voiced_frames.append(buf_chunk)
                        ring_buffer.clear()
                        silence_start = None
                else:
                    # 已触发，记录语音
                    voiced_frames.append(chunk)

                    if is_speech:
                        # 有语音，重置静音计时
                        silence_start = None
                    else:
                        # 静音
                        if silence_start is None:
                            silence_start = time.time()
                        else:
                            silence_duration = time.time() - silence_start
                            if silence_duration >= self.config.SILENCE_THRESHOLD:
                                # 检查录音时长
                                recording_duration = time.time() - start_time
                                if recording_duration >= self.config.MIN_RECORDING_SECONDS:
                                    logger.info(f"🔇 检测到 {silence_duration:.1f}s 静音，停止录音")
                                    play_sound(self.config.SOUND_END, self.config)
                                    break
                                else:
                                    # 录音时间太短，继续
                                    silence_start = None

        finally:
            stream.stop_stream()
            stream.close()

        # 检查是否录到有效语音
        if not triggered or len(voiced_frames) == 0:
            logger.warning("❌ 未检测到有效语音")
            return None

        # 转换为 WAV 格式
        return self._frames_to_wav(voiced_frames)

    def _frames_to_wav(self, frames: list) -> bytes:
        """将音频帧转换为 WAV 格式"""
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
            wav_path = f.name

        try:
            with wave.open(wav_path, 'wb') as wf:
                wf.setnchannels(self.config.CHANNELS)
                wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
                wf.setframerate(self.config.SAMPLE_RATE)
                wf.writeframes(b''.join(frames))

            with open(wav_path, 'rb') as f:
                wav_data = f.read()

            return wav_data
        finally:
            if os.path.exists(wav_path):
                os.remove(wav_path)

    def cleanup(self):
        """清理资源"""
        self.audio.terminate()


# ===========================================
# Whisper API 调用
# ===========================================

class WhisperClient:
    """Whisper API 客户端"""

    def __init__(self, config: Config):
        self.config = config

    def transcribe(self, audio_data: bytes) -> Optional[str]:
        """
        调用 Whisper API 进行转录

        Args:
            audio_data: WAV 格式音频数据

        Returns:
            str: 转录文本，失败返回 None
        """
        logger.info("🧠 正在转录...")

        try:
            # 保存临时文件
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                f.write(audio_data)
                temp_path = f.name

            try:
                # 调用 API
                with open(temp_path, 'rb') as f:
                    files = {'file': ('audio.wav', f, 'audio/wav')}
                    data = {'language': self.config.WHISPER_LANGUAGE}

                    response = requests.post(
                        self.config.WHISPER_API_URL,
                        files=files,
                        data=data,
                        timeout=30
                    )

                if response.status_code == 200:
                    result = response.json()
                    text = result.get('text', '').strip()

                    if text:
                        logger.info(f"✅ 转录成功: {text}")
                        return text
                    else:
                        logger.warning("⚠️  转录结果为空")
                        return None
                else:
                    logger.error(f"❌ API 调用失败: {response.status_code} - {response.text}")
                    return None

            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)

        except requests.exceptions.ConnectionError:
            logger.error("❌ 无法连接到 Whisper 服务，请确保服务已启动")
            logger.error("   运行: whisper-service start")
            return None
        except Exception as e:
            logger.error(f"❌ 转录失败: {e}")
            return None


# ===========================================
# 键盘输入模拟
# ===========================================

class KeyboardTyper:
    """键盘输入模拟器"""

    def __init__(self, config: Config):
        self.config = config
        self.keyboard = Controller()

    def type_text(self, text: str):
        """
        模拟键盘输入文本

        Args:
            text: 要输入的文本
        """
        logger.info(f"⌨️  正在输入文本...")

        # 等待一小段时间，确保焦点在正确的窗口
        time.sleep(0.2)

        # 逐字符输入
        for char in text:
            self.keyboard.type(char)
            if self.config.TYPING_DELAY > 0:
                time.sleep(self.config.TYPING_DELAY)

        logger.info("✅ 输入完成")

    def press_enter(self):
        """按下 Enter 键"""
        logger.info("↩️  按下 Enter 提交")
        time.sleep(0.1)
        self.keyboard.press(Key.enter)
        self.keyboard.release(Key.enter)


# ===========================================
# 主程序
# ===========================================

def main():
    """主函数"""
    config = Config()

    # 初始化组件
    recorder = VoiceRecorder(config)
    whisper = WhisperClient(config)
    typer = KeyboardTyper(config)

    try:
        # 1. 录音
        audio_data = recorder.record()
        if audio_data is None:
            logger.error("❌ 录音失败")
            return 1

        # 2. 转录
        text = whisper.transcribe(audio_data)
        if text is None:
            logger.error("❌ 转录失败")
            return 1

        # 检查是否为空文本或仅包含空白字符
        if not text or not text.strip():
            logger.warning("❌ 未识别到有效文本，跳过输入")
            return 1

        # 3. 输入文本
        typer.type_text(text)

        # 4. 自动提交
        if config.AUTO_SUBMIT:
            typer.press_enter()

        logger.info("🎉 完成！")
        return 0

    except KeyboardInterrupt:
        logger.info("\n⚠️  用户中断")
        return 1
    except Exception as e:
        logger.error(f"❌ 发生错误: {e}")
        return 1
    finally:
        recorder.cleanup()


if __name__ == "__main__":
    sys.exit(main())
