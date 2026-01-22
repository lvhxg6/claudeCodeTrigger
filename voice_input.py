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
import asyncio
import base64
from pathlib import Path
from typing import Optional

import yaml
import pyaudio
import webrtcvad
import requests
import websockets
from pynput.keyboard import Controller, Key

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.absolute()
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)


# ===========================================
# 配置文件加载
# ===========================================

def load_config() -> dict:
    """加载配置文件"""
    config_path = PROJECT_ROOT / "config.yaml"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return {}


# 全局配置
CONFIG = load_config()


# ===========================================
# 配置参数
# ===========================================

class Config:
    """配置类 - 从 config.yaml 读取"""

    def __init__(self):
        # STT 引擎配置
        stt = CONFIG.get("stt", {})
        self.STT_ENGINE = stt.get("engine", "whisper")
        self.STREAMING_MODE = stt.get("streaming", False)

        # Whisper 配置
        whisper = CONFIG.get("whisper", {})
        self.WHISPER_API_URL = whisper.get("api_url", "http://localhost:8765/v1/audio/transcriptions")
        self.WHISPER_LANGUAGE = whisper.get("language", None)

        # FunASR 配置
        funasr = CONFIG.get("funasr", {})
        self.FUNASR_API_URL = funasr.get("api_url", "http://localhost:10095/v1/audio/transcriptions")
        self.FUNASR_WS_URL = funasr.get("ws_url", "ws://localhost:10095/ws/transcribe")

        # 音频录制配置
        audio = CONFIG.get("audio", {})
        self.SAMPLE_RATE = audio.get("sample_rate", 16000)
        self.CHANNELS = audio.get("channels", 1)
        self.CHUNK_DURATION_MS = audio.get("chunk_duration_ms", 30)
        self.PADDING_DURATION_MS = audio.get("padding_duration_ms", 300)

        # VAD 配置
        vad = CONFIG.get("vad", {})
        self.VAD_MODE = vad.get("mode", 3)
        self.SILENCE_THRESHOLD = vad.get("silence_threshold", 1.5)
        self.MIN_RECORDING_SECONDS = vad.get("min_recording_seconds", 0.5)
        self.MAX_RECORDING_SECONDS = vad.get("max_recording_seconds", 60)

        # 键盘配置
        keyboard = CONFIG.get("keyboard", {})
        self.TYPING_DELAY = keyboard.get("typing_delay", 0.01)
        self.AUTO_SUBMIT = keyboard.get("auto_submit", False)

        # 声音配置
        sound = CONFIG.get("sound", {})
        self.ENABLE_SOUND = sound.get("enabled", True)
        self.SOUND_START = sound.get("start", "/System/Library/Sounds/Tink.aiff")
        self.SOUND_DETECTED = sound.get("detected", "/System/Library/Sounds/Pop.aiff")
        self.SOUND_END = sound.get("end", "/System/Library/Sounds/Tink.aiff")


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


def remove_repetition(text: str, threshold: int = 3) -> str:
    """
    去除文本中的重复片段

    Args:
        text: 原始文本
        threshold: 重复次数阈值，超过此次数则认为是异常重复

    Returns:
        去重后的文本
    """
    import re

    # 检测连续重复的词或短语（2-10个字符）
    # 例如："所有所有所有所有" -> "所有"
    for length in range(2, 11):
        # 匹配连续重复 threshold 次以上的片段
        pattern = r'(.{' + str(length) + r'})\1{' + str(threshold - 1) + r',}'
        text = re.sub(pattern, r'\1', text)

    # 检测句末重复（处理类似 "...所有所有所有。" 的情况）
    # 去除句末连续重复的短语
    text = re.sub(r'(.{2,6}?)(\1){2,}([。！？]?)$', r'\1\3', text)

    return text.strip()


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
# STT API 调用
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
                        # 去除重复片段（如 "所有所有所有..." -> "所有"）
                        text = remove_repetition(text)
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


class FunASRClient:
    """FunASR HTTP 客户端（非流式）"""

    def __init__(self, config: Config):
        self.config = config

    def transcribe(self, audio_data: bytes) -> Optional[str]:
        """
        调用 FunASR API 进行转录

        Args:
            audio_data: WAV 格式音频数据

        Returns:
            str: 转录文本，失败返回 None
        """
        logger.info("🧠 正在转录（FunASR）...")

        try:
            # 保存临时文件
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                f.write(audio_data)
                temp_path = f.name

            try:
                # 调用 API
                with open(temp_path, 'rb') as f:
                    files = {'file': ('audio.wav', f, 'audio/wav')}

                    response = requests.post(
                        self.config.FUNASR_API_URL,
                        files=files,
                        timeout=30
                    )

                if response.status_code == 200:
                    result = response.json()
                    text = result.get('text', '').strip()

                    if text:
                        # 去除重复片段
                        text = remove_repetition(text)
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
            logger.error("❌ 无法连接到 FunASR 服务，请确保服务已启动")
            logger.error("   运行: funasr-service start")
            return None
        except Exception as e:
            logger.error(f"❌ 转录失败: {e}")
            return None


class FunASRStreamingClient:
    """FunASR WebSocket 客户端（流式）"""

    def __init__(self, config: Config):
        self.config = config
        self.ws = None
        self.last_text = ""
        self.output_char_count = 0  # 已输出的字符数
        # 协程间通信
        self.stop_event = asyncio.Event()  # 停止信号
        self.result_queue = asyncio.Queue()  # 结果队列

    async def connect(self):
        """建立 WebSocket 连接"""
        logger.info(f"🔌 连接到 FunASR 流式服务: {self.config.FUNASR_WS_URL}")
        self.ws = await websockets.connect(self.config.FUNASR_WS_URL)
        logger.info("✅ WebSocket 连接成功")

    async def send_audio_chunk(self, chunk: bytes, is_final: bool = False):
        """发送音频块（原始 PCM 数据）"""
        if not self.ws:
            raise RuntimeError("WebSocket 未连接")

        # 直接 Base64 编码原始 PCM 数据（不添加 WAV 头）
        audio_base64 = base64.b64encode(chunk).decode()

        # 发送消息
        await self.ws.send(json.dumps({
            "type": "audio",
            "data": audio_base64,
            "is_final": is_final,
            # 添加音频格式信息
            "format": {
                "sample_rate": self.config.SAMPLE_RATE,
                "channels": self.config.CHANNELS,
                "sample_width": 2  # 16-bit
            }
        }))

    async def receive_result(self) -> Optional[str]:
        """接收识别结果，返回增量文本"""
        if not self.ws:
            return None

        try:
            # 等待接收消息（超时 5.0 秒，给服务端足够的推理时间）
            result = await asyncio.wait_for(self.ws.recv(), timeout=5.0)
            data = json.loads(result)

            if data.get("type") == "error":
                logger.error(f"❌ 服务端错误: {data.get('error')}")
                return None

            new_text = data.get("text", "")

            # 计算增量（只返回新增的部分）
            if new_text.startswith(self.last_text):
                increment = new_text[len(self.last_text):]
            else:
                # 如果不是前缀，说明有修正，返回完整文本
                increment = new_text
                self.last_text = ""

            self.last_text = new_text
            return increment if increment else None

        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.error(f"❌ 接收消息失败: {e}")
            return None

    async def receive_loop(self):
        """持续接收识别结果的协程"""
        logger.debug("接收协程启动")
        while not self.stop_event.is_set():
            try:
                # 短超时，确保能及时响应 stop_event
                result = await asyncio.wait_for(self.ws.recv(), timeout=0.1)
                data = json.loads(result)
                logger.debug(f"收到服务端消息: {data}")

                if data.get("type") == "error":
                    logger.error(f"服务端错误: {data.get('error')}")
                    continue

                new_text = data.get("text", "")

                # 简单的增量计算：只输出超过已输出字符数的新字符
                # 这样即使模型修正了之前的文字，也不会重复输出
                if len(new_text) > self.output_char_count:
                    increment = new_text[self.output_char_count:]
                    self.output_char_count = len(new_text)
                else:
                    # 模型修正导致文本变短或不变，不输出
                    increment = ""

                self.last_text = new_text

                if increment:
                    logger.info(f"📝 识别增量: {increment}")
                    await self.result_queue.put(increment)

            except asyncio.TimeoutError:
                continue  # 无数据，继续循环
            except websockets.exceptions.ConnectionClosed:
                logger.info("WebSocket 连接已关闭（接收协程）")
                break
            except Exception as e:
                logger.error(f"接收消息失败: {e}")
                break
        logger.debug("接收协程退出")

    async def close(self):
        """关闭连接"""
        if self.ws:
            await self.ws.close()
            logger.info("🔌 WebSocket 连接已关闭")


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

def create_stt_client(config: Config):
    """根据配置创建 STT 客户端"""
    if config.STT_ENGINE == "funasr":
        if config.STREAMING_MODE:
            return FunASRStreamingClient(config)
        else:
            return FunASRClient(config)
    else:
        return WhisperClient(config)


def main_batch():
    """主函数（非流式模式）"""
    config = Config()

    # 初始化组件
    recorder = VoiceRecorder(config)
    stt_client = create_stt_client(config)
    typer = KeyboardTyper(config)

    try:
        # 1. 录音
        audio_data = recorder.record()
        if audio_data is None:
            logger.error("❌ 录音失败")
            return 1

        # 2. 转录
        text = stt_client.transcribe(audio_data)
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


async def main_streaming():
    """主函数（流式模式）- 使用协程分离解决延迟问题"""
    config = Config()

    # 初始化组件
    streaming_client = FunASRStreamingClient(config)
    typer = KeyboardTyper(config)

    # 音频相关变量
    audio = None
    stream = None

    try:
        # 1. 连接到流式服务
        await streaming_client.connect()

        # 2. 开始录音并流式发送
        logger.info("🎙️  开始录音（流式模式），请说话...")
        play_sound(config.SOUND_START, config)

        # 打开音频流
        audio = pyaudio.PyAudio()
        chunk_size = int(config.SAMPLE_RATE * config.CHUNK_DURATION_MS / 1000)

        stream = audio.open(
            format=pyaudio.paInt16,
            channels=config.CHANNELS,
            rate=config.SAMPLE_RATE,
            input=True,
            frames_per_buffer=chunk_size
        )

        vad = webrtcvad.Vad(config.VAD_MODE)

        # 等待一小段时间，确保焦点在正确的窗口
        time.sleep(0.2)

        # 启动接收协程
        recv_task = asyncio.create_task(streaming_client.receive_loop())

        # 启动输出协程：从队列获取增量文本并输入
        async def output_loop():
            logger.debug("输出协程启动")
            while not streaming_client.stop_event.is_set():
                try:
                    increment = await asyncio.wait_for(
                        streaming_client.result_queue.get(),
                        timeout=0.1
                    )
                    logger.debug(f"输出协程收到文本: {increment}")
                    for char in increment:
                        typer.keyboard.type(char)
                        if config.TYPING_DELAY > 0:
                            await asyncio.sleep(config.TYPING_DELAY)
                except asyncio.TimeoutError:
                    continue
                except asyncio.CancelledError:
                    break
            logger.debug("输出协程退出")

        output_task = asyncio.create_task(output_loop())

        # 主循环：发送音频 + 静音检测（不再阻塞等待接收）
        triggered = False
        silence_start = None
        start_time = time.time()

        try:
            while True:
                # 检查是否超时
                elapsed = time.time() - start_time
                if elapsed > config.MAX_RECORDING_SECONDS:
                    logger.warning("⏱️  录音超时，自动停止")
                    # 发送结束信号
                    await streaming_client.send_audio_chunk(b'', is_final=True)
                    break

                # 读取音频块
                chunk = stream.read(chunk_size, exception_on_overflow=False)

                # VAD 检测
                is_speech = vad.is_speech(chunk, config.SAMPLE_RATE)

                if not triggered and is_speech:
                    triggered = True
                    logger.info("🗣️  检测到语音，开始流式识别...")
                    play_sound(config.SOUND_DETECTED, config)

                if triggered:
                    # 发送音频块到服务端
                    await streaming_client.send_audio_chunk(chunk, is_final=False)

                    # 检测静音（不再被接收阻塞！）
                    if is_speech:
                        silence_start = None
                    else:
                        if silence_start is None:
                            silence_start = time.time()
                        else:
                            silence_duration = time.time() - silence_start
                            if silence_duration >= config.SILENCE_THRESHOLD:
                                recording_duration = time.time() - start_time
                                if recording_duration >= config.MIN_RECORDING_SECONDS:
                                    logger.info(f"🔇 检测到 {silence_duration:.1f}s 静音，停止录音")
                                    play_sound(config.SOUND_END, config)

                                    # 发送结束信号
                                    await streaming_client.send_audio_chunk(b'', is_final=True)
                                    break

                # 让出控制权，让接收和输出协程有机会运行
                await asyncio.sleep(0)

        finally:
            if stream:
                stream.stop_stream()
                stream.close()
            if audio:
                audio.terminate()

        # 等待最终结果（服务端推理可能需要几秒钟）
        # 持续等待直到超时或收到结果
        wait_start = time.time()
        max_wait_time = 15.0  # 最多等待 15 秒（FunASR CPU 推理可能需要 8+ 秒）
        last_result_time = time.time()
        idle_timeout = 10.0  # 等待服务端推理完成（FunASR CPU 推理需要约 8 秒）

        logger.info("⏳ 等待服务端返回最终识别结果...")

        while time.time() - wait_start < max_wait_time:
            try:
                increment = await asyncio.wait_for(
                    streaming_client.result_queue.get(),
                    timeout=0.1
                )
                if increment:
                    logger.info(f"📝 收到识别结果: {increment}")
                    for char in increment:
                        typer.keyboard.type(char)
                        if config.TYPING_DELAY > 0:
                            await asyncio.sleep(config.TYPING_DELAY)
                    last_result_time = time.time()
            except asyncio.TimeoutError:
                # 检查是否已经空闲超过 idle_timeout
                if time.time() - last_result_time >= idle_timeout:
                    logger.debug("空闲超时，停止等待")
                    break
                continue

        # 设置停止信号
        streaming_client.stop_event.set()

        # 处理队列中剩余的结果
        while not streaming_client.result_queue.empty():
            try:
                increment = streaming_client.result_queue.get_nowait()
                for char in increment:
                    typer.keyboard.type(char)
                    if config.TYPING_DELAY > 0:
                        await asyncio.sleep(config.TYPING_DELAY)
            except asyncio.QueueEmpty:
                break

        # 取消协程任务
        recv_task.cancel()
        output_task.cancel()

        # 等待任务完成
        try:
            await asyncio.gather(recv_task, output_task, return_exceptions=True)
        except asyncio.CancelledError:
            pass

        # 检查是否录到有效语音
        if not triggered:
            logger.warning("❌ 未检测到有效语音")
            return 1

        # 自动提交
        if config.AUTO_SUBMIT:
            typer.press_enter()

        logger.info("🎉 完成！")
        return 0

    except KeyboardInterrupt:
        logger.info("\n⚠️  用户中断")
        return 1
    except Exception as e:
        logger.error(f"❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # 确保资源被清理
        streaming_client.stop_event.set()
        await streaming_client.close()


def main():
    """主函数入口"""
    config = Config()

    logger.info(f"🚀 启动语音输入 - 引擎: {config.STT_ENGINE}, 流式: {config.STREAMING_MODE}")

    if config.STT_ENGINE == "funasr" and config.STREAMING_MODE:
        # 流式模式（异步）
        return asyncio.run(main_streaming())
    else:
        # 非流式模式（同步）
        return main_batch()


if __name__ == "__main__":
    sys.exit(main())
