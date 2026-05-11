"""
构建脚本 — 将 AI Shell 打包为单文件可执行程序
用法: python build.py
"""

import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).parent

# 需要打包的资源文件
DATAS = [
    ("prompts", "prompts"),
    ("web", "web"),
    ("config.yaml", "."),
]

# 隐式导入
HIDDEN_IMPORTS = [
    "config",
    "llm",
    "tools",
    "context",
    "sanitize",
    "self_update",
    "paths",
    "setup",
    "server",
    "shell",
    "yaml",
    "requests",
]


def build():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", "ai-shell",
        "--console",
        "--clean",
    ]

    # 添加数据文件
    for src, dst in DATAS:
        src_path = PROJECT / src
        if src_path.exists():
            cmd.extend(["--add-data", f"{src_path};{dst}"])
        else:
            print(f"[WARN] {src_path} not found, skipping")

    # 添加隐式导入
    for mod in HIDDEN_IMPORTS:
        cmd.extend(["--hidden-import", mod])

    # 入口
    cmd.append(str(PROJECT / "main.py"))

    print(f"[BUILD] Running: {' '.join(cmd)}")
    print()

    result = subprocess.run(cmd, cwd=str(PROJECT))

    if result.returncode == 0:
        exe = PROJECT / "dist" / "ai-shell.exe"
        if exe.exists():
            size_mb = exe.stat().st_size / 1024 / 1024
            print(f"\n[BUILD] Success: {exe} ({size_mb:.1f} MB)")
        else:
            print(f"\n[BUILD] Done, check dist/ directory")
    else:
        print(f"\n[BUILD] Failed with code {result.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    build()
