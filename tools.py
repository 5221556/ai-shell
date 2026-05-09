"""
tools.py - 工具层（同步版）
内置工具 + 创造空间动态加载
"""

import os
import json
import subprocess
import importlib.util
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any
from paths import BASE_DIR, RESOURCE_DIR


@dataclass
class ToolResult:
    success: bool
    data: Any = None
    error: str = ""


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Any = field(repr=False)


SYSTEM_EXTENSIONS = {".py", ".yaml", ".yml"}


def _is_system_file(path: Path) -> bool:
    """判断是否为系统源文件（修改前需备份）"""
    suffix = path.suffix.lower()
    if suffix in SYSTEM_EXTENSIONS:
        return True
    parts = path.parts
    if len(parts) >= 2 and parts[-2] in ("prompts",):
        return True
    return False


def _auto_backup(path: Path):
    """写入系统文件前自动备份当前版本"""
    try:
        from self_update import VersionManager
        vm = VersionManager(path.parent if path.parent.exists() else None)
        if not path.exists():
            return
        backup_dir = vm.backups_dir / "auto"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_file = backup_dir / path.name
        import shutil
        shutil.copy2(path, backup_file)
    except Exception:
        pass


# ========== 内置工具 ==========

def _read(path: str) -> ToolResult:
    try:
        p = Path(path).expanduser().resolve()
        if not p.exists():
            return ToolResult(False, error=f"文件不存在: {path}")
        if not p.is_file():
            return ToolResult(False, error=f"不是文件: {path}")
        content = p.read_text(encoding="utf-8", errors="replace")
        return ToolResult(True, data=content)
    except Exception as e:
        return ToolResult(False, error=str(e))


def _write(path: str, content: str) -> ToolResult:
    try:
        p = Path(path).expanduser().resolve()
        if _is_system_file(p):
            _auto_backup(p)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return ToolResult(True, data=f"已写入: {path}")
    except Exception as e:
        return ToolResult(False, error=str(e))


def _exec(command: str, timeout: int = 30) -> ToolResult:
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return ToolResult(False, data=result.stdout, error=result.stderr)
        return ToolResult(True, data=result.stdout if result.stdout else "(无输出)")
    except subprocess.TimeoutExpired:
        return ToolResult(False, error=f"命令超时 ({timeout}s)")
    except Exception as e:
        return ToolResult(False, error=str(e))


def _search_context(query: str, n: int = 10) -> ToolResult:
    """搜索归档的对话上下文"""
    try:
        archive_dir = BASE_DIR / "context" / "archives"
        if not archive_dir.exists():
            return ToolResult(True, data="（无归档上下文）")

        results = []
        query_lower = query.lower()

        for archive_file in sorted(archive_dir.glob("*.jsonl"), reverse=True):
            try:
                with open(archive_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            msg = json.loads(line)
                            content = msg.get("content", "")
                            if query_lower in content.lower():
                                results.append({
                                    "role": msg.get("role", ""),
                                    "content": content[:500],
                                    "date": archive_file.stem,
                                })
                                if len(results) >= n:
                                    break
                        except json.JSONDecodeError:
                            continue
                if len(results) >= n:
                    break
            except Exception:
                continue

        if not results:
            return ToolResult(True, data=f"未找到与 '{query}' 相关的历史上下文")
        return ToolResult(True, data=json.dumps(results, ensure_ascii=False, indent=2))
    except Exception as e:
        return ToolResult(False, error=str(e))


# ========== 内置工具注册 ==========

BUILTIN_TOOLS: dict[str, Tool] = {
    "read": Tool(
        name="read",
        description="读取文件内容",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"}
            },
            "required": ["path"],
        },
        handler=_read,
    ),
    "write": Tool(
        name="write",
        description="写入文件内容",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "文件路径"},
                "content": {"type": "string", "description": "写入内容"},
            },
            "required": ["path", "content"],
        },
        handler=_write,
    ),
    "exec": Tool(
        name="exec",
        description="执行系统命令",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "要执行的命令"}
            },
            "required": ["command"],
        },
        handler=_exec,
    ),
    "search_context": Tool(
        name="search_context",
        description="搜索历史对话上下文。当用户提到之前聊过的内容、或你想回忆之前的对话时使用。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "n": {"type": "integer", "description": "返回条数（默认10）"}
            },
            "required": ["query"],
        },
        handler=_search_context,
    ),
}


# ========== 创造空间动态加载 ==========

TOOLS: dict[str, Tool] = dict(BUILTIN_TOOLS)


def _load_creative_tools():
    """扫描 creative_space/tools/ 加载动态工具"""
    global TOOLS

    # 保留内置工具
    TOOLS = dict(BUILTIN_TOOLS)

    tools_dir = BASE_DIR / "creative_space" / "tools"
    if not tools_dir.exists():
        return 0

    loaded = 0
    for py_file in sorted(tools_dir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        try:
            # 动态加载模块
            spec = importlib.util.spec_from_file_location(
                f"creative_tool_{py_file.stem}", str(py_file)
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 提取工具定义
            if not hasattr(module, "TOOL_DEFINITION") or not hasattr(module, "handler"):
                continue

            defn = module.TOOL_DEFINITION
            name = defn.get("name", py_file.stem)

            TOOLS[name] = Tool(
                name=name,
                description=defn.get("description", ""),
                parameters=defn.get("parameters", {"type": "object", "properties": {}}),
                handler=module.handler,
            )
            loaded += 1
        except Exception as e:
            print(f"[创造空间] 加载 {py_file.name} 失败: {e}")

    return loaded


def reload_tools() -> dict:
    """热加载创造空间工具，返回统计信息"""
    before = len(TOOLS)
    count = _load_creative_tools()
    after = len(TOOLS)
    return {
        "before": before,
        "after": after,
        "loaded": count,
        "tools": list(TOOLS.keys()),
    }


# 启动时加载一次
_load_creative_tools()


# ========== 接口 ==========

def get_tool_definitions() -> list:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in TOOLS.values()
    ]


def execute_tool(name: str, args: dict) -> ToolResult:
    tool = TOOLS.get(name)
    if not tool:
        return ToolResult(False, error=f"未知工具: {name}")
    result = tool.handler(**args)
    # 兼容创造空间工具返回 dict
    if isinstance(result, dict):
        return ToolResult(
            success=result.get("success", True),
            data=result.get("data"),
            error=result.get("error", ""),
        )
    return result
