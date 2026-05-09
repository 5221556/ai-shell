"""
paths.py - 路径管理
打包模式：资源文件从 exe 临时目录读取，数据写入 exe 同级目录
开发模式：一切在源码目录
"""

import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    # PyInstaller 打包模式
    RESOURCE_DIR = Path(sys._MEIPASS)       # 只读资源（prompts/, web/, config.yaml）
    BASE_DIR = Path(sys.executable).parent  # 可写数据（logs/, context/, backups/）
else:
    # 开发模式
    RESOURCE_DIR = Path(__file__).parent
    BASE_DIR = RESOURCE_DIR

# 确保可写目录存在
for d in ["logs", "context/archives", "backups/auto", "versions",
          "creative_space/tools", "creative_space/scripts", "creative_space/notes"]:
    (BASE_DIR / d).mkdir(parents=True, exist_ok=True)
