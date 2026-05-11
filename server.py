"""
server.py - AI Shell 后端（同步版）
使用 ThreadingHTTPServer 处理并发
v2: 上下文分层管理 + 自我更新
"""

import os
import json
import re
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

from paths import BASE_DIR, RESOURCE_DIR
from config import load_config
from llm import LLMClient
from tools import get_tool_definitions, execute_tool
from context import ContextManager
from self_update import (
    ErrorLogger, VersionManager, detect_correction,
    UNIFIED_ANALYSIS_PROMPT, EXECUTION_PROMPT,
)
from sanitize import sanitizer

def load_prompt(name: str) -> str:
    with open(RESOURCE_DIR / "prompts" / name, encoding="utf-8") as f:
        return f.read()

# ========== 全局状态 ==========

config = load_config()
chat_prompt = load_prompt("chat.txt")
tool_prompt = load_prompt("tool.txt")
tool_defs = get_tool_definitions()

ctx_mgr = ContextManager(BASE_DIR, max_active=config.get("context", {}).get("max_active", 20))
error_logger = ErrorLogger(BASE_DIR)
version_mgr = VersionManager(BASE_DIR)

_thread_local = threading.local()

def get_chat_llm() -> LLMClient:
    if not hasattr(_thread_local, "chat_llm"):
        _thread_local.chat_llm = LLMClient(config["chat_ai"])
        if not sanitizer._llm_client:
            sanitizer.set_llm_client(_thread_local.chat_llm)
    return _thread_local.chat_llm

def get_tool_llm() -> LLMClient:
    if not hasattr(_thread_local, "tool_llm"):
        _thread_local.tool_llm = LLMClient(config["tool_ai"])
    return _thread_local.tool_llm

_last_ai_reply_lock = threading.Lock()
_last_ai_reply: str = ""


# ========== 双AI引擎 ==========

def do_chat(user_input: str) -> list:
    """完整对话流程。支持多轮工具调用。"""
    global _last_ai_reply
    chat_llm = get_chat_llm()
    tool_llm = get_tool_llm()
    chunks = []

    user_input = sanitizer.sanitize(user_input)

    messages = [{"role": "system", "content": chat_prompt}]
    messages.extend(ctx_mgr.get_messages())
    messages.append({"role": "user", "content": user_input})

    # 多轮工具调用循环
    max_rounds = 5
    for round_num in range(max_rounds):
        try:
            resp = chat_llm.chat(messages, tools=tool_defs)
        except Exception as e:
            error_logger.log_llm_error(context="chat_ai call", error_body=str(e))
            return [f"❌ AI 调用失败: {e}"]

        msg = resp["choices"][0]["message"]

        # 不需要工具——直接流式回复
        if not msg.get("tool_calls"):
            full = ""
            try:
                for chunk in chat_llm.stream(messages):
                    full += chunk
                    chunks.append(chunk)
            except Exception as e:
                error_logger.log_llm_error(context="chat_ai stream", error_body=str(e))
                full = f"[流式输出中断: {e}]"
                chunks.append(full)

            ctx_mgr.add_pair(user_input, full)

            with _last_ai_reply_lock:
                prev = _last_ai_reply
                _last_ai_reply = full
            if detect_correction(user_input) and prev:
                error_logger.log_ai_correction(user_input, prev)
            return chunks

        # 执行工具
        if round_num == 0:
            chunks.append("⏳ 正在执行任务...\n\n")

        # 把 assistant 的工具调用加入 messages
        messages.append(msg)

        tool_results = []
        for tc in msg["tool_calls"]:
            func = tc["function"]
            args = json.loads(func["arguments"])
            chunks.append(f"🔧 调用 {func['name']}...\n")
            result = execute_tool(func["name"], args)

            tr = {
                "tool_call_id": tc["id"],
                "tool": func["name"],
                "success": result.success,
                "data": result.data,
                "error": result.error,
            }
            tool_results.append(tr)

            if result.success:
                chunks.append(f"✅ {func['name']} 完成\n")
            else:
                chunks.append(f"❌ {func['name']} 失败: {result.error}\n")
                error_logger.log_tool_error(func["name"], user_input, result.error, args)

        # 把工具结果加入 messages
        for tr in tool_results:
            messages.append({
                "role": "tool",
                "tool_call_id": tr["tool_call_id"],
                "content": json.dumps(tr, ensure_ascii=False),
            })

    # 超过最大轮数
    chunks.append("⚠️ 达到最大工具调用轮数\n")
    return chunks


# ========== 错误日志驱动的自我分析 ==========

def do_self_update() -> list:
    """错误日志自我分析（用户显式触发）"""
    chat_llm = get_chat_llm()
    tool_llm = get_tool_llm()
    chunks = []

    chunks.append("📦 检查版本归档...\n")
    try:
        version_mgr.ensure_v1_archived()
        chunks.append(f"✅ 当前版本: {version_mgr.get_current_version()}\n\n")
    except Exception as e:
        chunks.append(f"⚠️ 归档失败: {e}\n\n")

    chunks.append("📋 读取错误日志...\n")
    logs = error_logger.get_logs(100)
    stats = error_logger.get_stats()

    if logs:
        chunks.append(f"🔢 共 {stats['total']} 条日志\n")
        for t, count in stats["by_type"].items():
            chunks.append(f"  - {t}: {count}\n")
    else:
        chunks.append("✅ 没有错误日志\n")

    chunks.append("\n🧠 AI 分析中...\n\n")
    log_text = json.dumps(logs, ensure_ascii=False, indent=2) if logs else "（无错误日志）"
    analysis_prompt = UNIFIED_ANALYSIS_PROMPT.format(
        log_summary=log_text,
        user_intent="（用户未明确指定，请基于错误日志判断是否需要修复bug）",
    )

    try:
        analysis_resp = chat_llm.chat([
            {"role": "system", "content": chat_prompt},
            {"role": "user", "content": f"请分析错误日志：\n\n{analysis_prompt}\n\n严格JSON格式返回。"},
        ])
    except Exception as e:
        error_logger.log_llm_error(context="self_update analysis", error_body=str(e))
        return [f"❌ 分析失败: {e}"]

    analysis_text = analysis_resp["choices"][0]["message"].get("content", "")
    chunks.append(f"📊 分析结果:\n{analysis_text[:1500]}\n\n")

    try:
        decision = _parse_decision(analysis_text)
    except Exception as e:
        error_logger.log_parse_error("self_update decision parse", str(e))
        chunks.append(f"⚠️ 解析失败: {e}\n")
        return chunks

    if decision.get("action") != "update":
        chunks.append("💡 当前不需要更新\n")
        chunks.append(f"理由: {decision.get('reasons', [])}\n")
        return chunks

    chunks.append(f"🔧 修复文件: {decision.get('files_to_modify', [])}\n")

    chunks.append("\n💾 创建备份...\n")
    try:
        backup_path = version_mgr.backup_current()
        chunks.append(f"✅ 备份到: {backup_path}\n")
    except Exception as e:
        chunks.append(f"⚠️ 备份失败: {e}\n")

    all_files = set(decision.get("files_to_modify", []))
    all_files.update(decision.get("files_to_read_first", []))
    if not all_files:
        all_files = {"tools.py", "server.py", "shell.py", "prompts/chat.txt", "prompts/tool.txt"}

    file_context = ""
    for fname in sorted(all_files):
        fp = BASE_DIR / fname
        if fp.exists():
            try:
                content = fp.read_text(encoding="utf-8", errors="replace")
                file_context += f"\n\n### {fname}\n```\n{content}\n```"
            except Exception:
                file_context += f"\n\n### {fname}\n```\n(无法读取)\n```"
        else:
            file_context += f"\n\n### {fname}\n```\n(文件不存在)\n```"

    exec_prompt = EXECUTION_PROMPT.format(
        file_contents=file_context,
        implementation_plan=decision.get("implementation_plan", ""),
    )

    chunks.append("\n⚙️ 工具AI执行修复...\n")
    try:
        fix_resp = tool_llm.chat([
            {"role": "system", "content": tool_prompt},
            {"role": "user", "content": exec_prompt + "\n\n必须使用 write 工具写入修改后的文件。"},
        ], tools=tool_defs)
    except Exception as e:
        error_logger.log_llm_error(context="self_update fix", error_body=str(e))
        chunks.append(f"❌ 修复失败: {e}\n")
        return chunks

    fix_msg = fix_resp["choices"][0]["message"]
    if fix_msg.get("tool_calls"):
        chunks.append("🔧 写入修改:\n")
        for tc in fix_msg["tool_calls"]:
            func = tc["function"]
            args = json.loads(func["arguments"])
            chunks.append(f"  🔧 {func['name']}({json.dumps(args, ensure_ascii=False)[:200]})\n")
            result = execute_tool(func["name"], args)
            if result.success:
                chunks.append(f"  ✅ 完成\n")
            else:
                chunks.append(f"  ❌ 失败: {result.error}\n")
    else:
        chunks.append(f"💬 {fix_msg.get('content', '(无内容)')[:500]}\n")

    chunks.append("\n🧪 测试新版本...\n")
    ok, msg = version_mgr.test_version(BASE_DIR)
    if ok:
        next_version = version_mgr.get_next_version()
        version_mgr.create_version(next_version)
        version_mgr.switch_version(next_version)
        chunks.append(f"✅ {msg}\n✅ 新版本: {next_version}\n⚠️ 请重启服务\n")
    else:
        chunks.append(f"❌ 测试失败: {msg}\n🔄 回滚...\n")
        try:
            version_mgr.restore_from_backup(backup_path)
            chunks.append("✅ 已回滚\n")
        except Exception as e:
            chunks.append(f"❌ 回滚失败: {e}\n")

    return chunks


def _parse_decision(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for pattern in [r'```json\s*([\s\S]*?)\s*```', r'```\s*([\s\S]*?)\s*```', r'\{[\s\S]*?"action"[\s\S]*?\}']:
        m = re.search(pattern, text)
        if m:
            try:
                return json.loads(m.group(1) if '```' in pattern else m.group(0))
            except json.JSONDecodeError:
                continue
    return {"action": "none", "reasons": ["无法解析"]}


# ========== HTTP 处理器 ==========

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", "/index.html"):
            self._serve(RESOURCE_DIR / "web" / "index.html", "text/html")
        elif p == "/api/errors":
            self._handle_get_errors()
        elif p == "/api/context":
            self._handle_get_context()
        elif p == "/api/reload-tools":
            self._handle_reload_tools()
        else:
            fp = RESOURCE_DIR / p.lstrip("/")
            if fp.is_file():
                self._serve(fp, self._guess(fp))
            else:
                self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path == "/api/chat":
            self._handle_chat()
        elif path == "/api/self-update":
            self._handle_self_update()
        else:
            self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def _stream_response(self, chunks: list):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self._cors()
        self.end_headers()
        try:
            for chunk in chunks:
                data = json.dumps({"content": chunk}, ensure_ascii=False)
                self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                self.wfile.flush()
        except Exception as e:
            err = json.dumps({"error": str(e)}, ensure_ascii=False)
            self.wfile.write(f"data: {err}\n\n".encode("utf-8"))
            self.wfile.flush()
        self.wfile.write(b"data: [DONE]\n\n")
        self.wfile.flush()

    def _handle_chat(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        msg = body.get("message", "").strip()
        if not msg:
            self._json({"error": "空消息"}, 400)
            return
        chunks = do_chat(msg)
        self._stream_response(chunks)

    def _handle_self_update(self):
        chunks = do_self_update()
        self._stream_response(chunks)

    def _handle_get_errors(self):
        self._json({"stats": error_logger.get_stats(), "logs": error_logger.get_logs(20)})

    def _handle_get_context(self):
        self._json({"stats": ctx_mgr.get_stats()})

    def _handle_reload_tools(self):
        from tools import reload_tools
        result = reload_tools()
        self._json(result)

    def _serve(self, path, ct):
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", f"{ct}; charset=utf-8")
        self.send_header("Content-Length", len(data))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(body))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _guess(self, p):
        ext = p.suffix.lower()
        return {".html": "text/html", ".js": "application/javascript", ".css": "text/css"}.get(ext, "text/plain")

    def log_message(self, format, *args):
        print(f"[AI Shell] {args[0]}")


# ========== 启动 ==========

def main():
    host, port = config["server"]["host"], config["server"]["port"]
    current_version = version_mgr.get_current_version()

    from tools import TOOLS
    tool_count = len(TOOLS)

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"""
╔══════════════════════════════════════╗
║          AI Shell v2 已启动          ║
║                                      ║
║  地址: http://{host}:{port}        ║
║  模型: {config['chat_ai']['model']:<24}║
║  版本: {current_version:<24}║
║  工具: {tool_count} 个 (含创造空间)         ║
║                                      ║
║  自然对话即可，AI自行判断执行        ║
║  Ctrl+C 停止                         ║
╚══════════════════════════════════════╝
""")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
        server.server_close()


if __name__ == "__main__":
    main()
