"""
self_update.py - 框架自我更新模块
v2 核心：错误日志收集 → AI自我分析 → 编写新版本 → 转接接管

设计原则：
- 不硬编码阈值、判断标准、更新范围，全部由AI自行决定
- 两条更新路径：
  路径A（错误驱动）：收集错误 → AI分析 → 修复bug
  路径B（功能驱动）：用户描述需求 → AI读代码 → 写新功能 → 发布
- 更新失败自动回滚
"""

import json
import time
import shutil
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Optional
from paths import BASE_DIR, RESOURCE_DIR


# =============================================================================
# 错误日志收集
# =============================================================================

class ErrorLogger:
    """收集系统运行错误到 logs/errors.jsonl"""

    ERROR_TYPES = ["tool_error", "ai_correction", "llm_error", "parse_error", "timeout", "user_request"]

    def __init__(self, project_root: Path = None):
        if project_root is None:
            project_root = BASE_DIR
        self.log_dir = Path(project_root) / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.log_dir / "errors.jsonl"

    def log(self, error_type: str, **details):
        """记录一条日志到 JSONL 文件"""
        entry = {
            "time": datetime.now(timezone.utc).isoformat(),
            "type": error_type,
        }
        entry.update({k: v for k, v in details.items() if v is not None})
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def log_tool_error(self, tool_name: str, user_input: str, error_msg: str, args: dict = None):
        """工具执行失败"""
        self.log("tool_error",
                 tool=tool_name,
                 user_input=user_input[:500],
                 error=error_msg[:500],
                 args=args)

    def log_ai_correction(self, user_input: str, previous_ai_reply: str):
        """用户纠正了AI的回答"""
        self.log("ai_correction",
                 user_input=user_input[:500],
                 previous_reply=previous_ai_reply[:500])

    def log_llm_error(self, status_code: int = None, error_body: str = None, context: str = ""):
        """LLM API 调用失败"""
        self.log("llm_error",
                 status_code=status_code,
                 error=error_body[:500] if error_body else None,
                 context=context[:300])

    def log_parse_error(self, context: str, detail: str = ""):
        """AI 输出格式错误"""
        self.log("parse_error",
                 context=context[:300],
                 detail=detail[:500])

    def log_timeout(self, context: str = ""):
        """超时"""
        self.log("timeout", context=context[:300])

    def log_user_request(self, user_input: str, category: str = "feature"):
        """用户请求了新功能或系统变更"""
        self.log("user_request",
                 user_input=user_input[:500],
                 category=category)

    def get_logs(self, n: int = 100) -> list:
        """获取最近 n 条日志"""
        if not self.log_path.exists():
            return []
        try:
            logs = []
            with open(self.log_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        logs.append(json.loads(line))
            return logs[-n:]
        except Exception:
            return []

    def get_stats(self) -> dict:
        """获取错误统计摘要"""
        logs = self.get_logs(200)
        if not logs:
            return {"total": 0, "by_type": {}, "recent": []}

        by_type = {}
        for entry in logs:
            t = entry.get("type", "unknown")
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "total": len(logs),
            "by_type": by_type,
            "recent": logs[-5:],
        }


# =============================================================================
# 版本管理
# =============================================================================

class VersionManager:
    """
    管理版本目录结构:

    {project_root}/
    ├── VERSION              ← 当前版本号（如 "v1"）
    ├── versions/
    │   ├── v1/              ← 历史版本（归档）
    │   └── v2/              ← 下一个版本
    └── backups/
        └── backup_<ts>/     ← 自动备份
    """

    SOURCE_FILES = ["server.py", "shell.py", "llm.py", "tools.py", "config.py", "self_update.py"]
    SOURCE_DIRS = ["prompts", "web", "logs"]

    def __init__(self, project_root: Path = None):
        if project_root is None:
            project_root = BASE_DIR
        self.root = Path(project_root)
        self.versions_dir = self.root / "versions"
        self.version_file = self.root / "VERSION"
        self.backups_dir = self.root / "backups"

    def get_current_version(self) -> str:
        """读取当前版本号"""
        if self.version_file.exists():
            v = self.version_file.read_text(encoding="utf-8").strip()
            if v:
                return v
        return "v1"

    def get_next_version(self) -> str:
        """计算下一个版本号"""
        current = self.get_current_version()
        try:
            num = int(current.lstrip("v"))
            return f"v{num + 1}"
        except ValueError:
            return "v2"

    def ensure_v1_archived(self) -> Path:
        """确保 v1 已被归档到 versions/ 目录"""
        v1_dir = self.versions_dir / "v1"
        v1_dir.mkdir(parents=True, exist_ok=True)

        for fname in self.SOURCE_FILES:
            src = self.root / fname
            if src.exists():
                shutil.copy2(src, v1_dir / fname)
        for dname in self.SOURCE_DIRS:
            src_dir = self.root / dname
            if src_dir.exists() and src_dir.is_dir():
                tgt_dir = v1_dir / dname
                if tgt_dir.exists():
                    shutil.rmtree(tgt_dir)
                shutil.copytree(src_dir, tgt_dir)

        return v1_dir

    def create_version(self, version: str = None) -> Path:
        """复制当前所有源文件到新版本目录"""
        if version is None:
            version = self.get_next_version()

        dst = self.versions_dir / version
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True, exist_ok=True)

        for fname in self.SOURCE_FILES:
            src = self.root / fname
            if src.exists():
                shutil.copy2(src, dst / fname)

        cfg = self.root / "config.yaml"
        if cfg.exists():
            shutil.copy2(cfg, dst / "config.yaml")

        for dname in self.SOURCE_DIRS:
            src_dir = self.root / dname
            if src_dir.exists() and src_dir.is_dir():
                tgt_dir = dst / dname
                if tgt_dir.exists():
                    shutil.rmtree(tgt_dir)
                shutil.copytree(src_dir, tgt_dir)

        print(f"[版本管理] 已创建版本 {version} -> {dst}")
        return dst

    def backup_current(self) -> Path:
        """创建当前版本的备份"""
        ts = int(time.time())
        dst = self.backups_dir / f"backup_{ts}"
        dst.mkdir(parents=True, exist_ok=True)

        for fname in self.SOURCE_FILES:
            src = self.root / fname
            if src.exists():
                shutil.copy2(src, dst / fname)

        cfg = self.root / "config.yaml"
        if cfg.exists():
            shutil.copy2(cfg, dst / "config.yaml")

        for dname in self.SOURCE_DIRS:
            src_dir = self.root / dname
            if src_dir.exists() and src_dir.is_dir():
                shutil.copytree(src_dir, dst / dname)

        print(f"[版本管理] 已备份到 {dst}")
        return dst

    def switch_version(self, version: str):
        """切换当前版本"""
        self.version_file.write_text(version, encoding="utf-8")
        print(f"[版本管理] VERSION -> {version}")

    def restore_from_backup(self, backup_path: Path):
        """从指定备份恢复文件到项目根目录"""
        for fname in self.SOURCE_FILES:
            src = backup_path / fname
            if src.exists():
                shutil.copy2(src, self.root / fname)

        cfg = backup_path / "config.yaml"
        if cfg.exists():
            shutil.copy2(cfg, self.root / "config.yaml")

        for dname in self.SOURCE_DIRS:
            src_dir = backup_path / dname
            if src_dir.exists() and src_dir.is_dir():
                tgt_dir = self.root / dname
                if tgt_dir.exists():
                    shutil.rmtree(tgt_dir)
                shutil.copytree(src_dir, tgt_dir)

        print(f"[版本管理] 已从 {backup_path} 恢复")

    def _py_compile_check(self, py_file: Path, cwd: Path) -> tuple:
        """检查 Python 文件语法"""
        try:
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", str(py_file)],
                capture_output=True, text=True, timeout=30,
                cwd=str(cwd)
            )
            if result.returncode != 0:
                return False, result.stderr[:500]
            return True, ""
        except subprocess.TimeoutExpired:
            return False, "编译检查超时"
        except Exception as e:
            return False, str(e)[:500]

    def test_version(self, version_dir: Path) -> tuple:
        """测试新版本能否通过基本检查"""
        py_files = [version_dir / f for f in self.SOURCE_FILES if f.endswith(".py")]
        errors = []
        for pf in py_files:
            ok, err = self._py_compile_check(pf, version_dir)
            if not ok:
                errors.append(f"{pf.name}: {err}")

        if errors:
            return False, "\n".join(errors)

        try:
            check_code = f"""
import sys
sys.path.insert(0, r'{version_dir}')
from tools import get_tool_definitions, execute_tool, TOOLS
from config import load_config
assert len(TOOLS) >= 3, '工具注册不完整'
assert callable(get_tool_definitions), 'get_tool_definitions 不可调用'
print('OK')
"""
            result = subprocess.run(
                [sys.executable, "-c", check_code],
                capture_output=True, text=True, timeout=30,
                cwd=str(version_dir)
            )
            if result.returncode != 0:
                return False, f"导入检查失败:\n{result.stderr[:500]}"
            return True, "所有检查通过"
        except subprocess.TimeoutExpired:
            return False, "导入检查超时"
        except Exception as e:
            return False, f"导入检查异常: {str(e)[:500]}"


# =============================================================================
# 统一自我分析提示词（同时处理错误和功能需求）
# =============================================================================

UNIFIED_ANALYSIS_PROMPT = """你是 AI Shell 系统的维护和进化专家。你的任务是综合分析系统运行日志和用户需求，决定如何更新系统。

## 系统文件说明
- server.py: Web 后端（ThreadingHTTPServer + SSE流式输出）
- shell.py: 终端版入口（REPL 循环）
- llm.py: LLM API 调用封装（OpenAI 兼容接口）
- tools.py: 工具定义与执行（read/write/exec 三个原语）
- config.yaml: 模型参数和服务端口配置
- config.py: 配置加载器
- prompts/chat.txt: 聊天AI的系统提示词
- prompts/tool.txt: 工具AI的系统提示词
- self_update.py: 自我更新模块（本模块）

## 系统运行日志
{log_summary}

## 用户需求
{user_intent}

## 你的分析任务
1. 理解用户需求的核心意图
2. 结合错误日志，判断哪些是bug、哪些是新功能
3. 判断需要修改哪些文件，以及每个文件需要改什么
4. 评估可行性：这个需求能否通过修改现有代码实现？

## 返回格式（严格JSON）
{{
  "action": "update" 或 "none",
  "update_type": "error_fix" 或 "feature_add" 或 "both",
  "confidence": 0.0 到 1.0,
  "reasons": ["理由1", "理由2"],
  "files_to_modify": ["tools.py", "prompts/tool.txt"],
  "files_to_read_first": ["server.py", "shell.py"],
  "problem_summary": "问题的简要描述或功能需求简述",
  "implementation_plan": "详细的实现方案：每个文件需要改什么、怎么改、为什么这样改。要足够具体，让执行者能直接据此写代码。"
}}

- 如果是bug修复：action="update", update_type="error_fix"
- 如果是新功能：action="update", update_type="feature_add"
- 如果既有bug又有功能需求：action="update", update_type="both"
- 如果不需要更新（需求不明确、不可行等）：action="none"
- implementation_plan 是核心，必须详细到文件级别"""


# =============================================================================
# 执行提示词（给工具AI的指令）
# =============================================================================

EXECUTION_PROMPT = """你是 AI Shell 的执行引擎。你的任务是直接修改系统源代码来实现需求。

## 当前代码

以下是需要关注的文件的完整内容：

{file_contents}

## 实施方案

{implementation_plan}

## 你的任务
1. 仔细阅读每个文件的当前代码，理解现有架构
2. 按照实施方案，确定每个文件需要做哪些修改
3. 使用 write 工具，将修改后的完整文件内容写入
4. 修改完成后，总结你做了什么修改

## 核心原则
- 必须使用 write 工具实际写入文件，不能只描述要做什么
- 保持接口兼容：不要破坏现有的函数签名和数据结构
- 遵循原有代码风格：缩进、命名、注释风格保持一致
- 最小修改原则：只改需要改的地方，不要重写整个文件
- 如果实现了新工具，必须在 tools.py 中正确注册
- 如果修改了提示词，必须使用 write 写入到 prompts/ 目录"""


# =============================================================================
# 意图检测
# =============================================================================

CORRECTION_KEYWORDS = [
    "不对", "错了", "错误", "不正确", "应该是",
    "改正", "修正", "更正", "纠正", "重新",
    "不对的", "不是这样", "你看错了",
    "wrong", "incorrect", "correct", "fix", "mistake",
]

def detect_correction(user_input: str) -> bool:
    """检测用户输入是否包含纠正意图（用于日志记录，非决策）"""
    text = user_input.lower()
    for kw in CORRECTION_KEYWORDS:
        if kw in text:
            return True
    return False
