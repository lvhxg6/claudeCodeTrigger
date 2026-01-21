#!/bin/bash
# 测试脚本 - 验证 Karabiner 是否能触发命令

echo "$(date): Voice input triggered!" >> /tmp/voice-input-test.log
/usr/local/bin/voice-input
