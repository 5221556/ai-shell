"""
AI Shell - 终端版
v2: 上下文分层管理 + 自我更新
"""

import os
import sys
import json
import re
import time
import yaml
from pathlib import Path

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


def do_chat(user_input: str, chat_llm: LLMClient, tool_llm: LLMClient,
            chat_prompt: str, tool_prompt: str, tool_defs: list,
            ctx_mgr: ContextManager, error_logger: ErrorLogger, last_reply: list) -> str:
    """一次完整对话。支持多轮工具调用。"""

    messages = [{"role": "system", "content": chat_prompt}]
    messages.extend(ctx_mgr.get_messages())
    messages.append({"role": "user", "content": user_input})

    # 多轮工具调用循环
    max_rounds = 20
    for round_num in range(max_rounds):
        try:
            resp = chat_llm.chat(messages, tools=tool_defs)
        except Exception as e:
            error_logger.log_llm_error(context="chat_ai call", error_body=str(e))
            return f"❌ AI 调用失败: {e}"

        msg = resp["choices"][0]["message"]

        if not msg.get("tool_calls"):
            reply = msg.get("content", "")
            if last_reply[0] and detect_correction(user_input):
                error_logger.log_ai_correction(user_input, last_reply[0])
            last_reply[0] = reply
            ctx_mgr.add_pair(user_input, reply)
            return reply

        # 执行工具
        if round_num == 0:
            print("  ⏳ 执行任务...")

        messages.append(msg)

        for tc in msg["tool_calls"]:
            func = tc["function"]
            args = json.loads(func["arguments"])
            print(f"  🔧 {func['name']}({json.dumps(args, ensure_ascii=False)[:120]})")
            t0 = time.time()
            result = execute_tool(func["name"], args)
            elapsed = time.time() - t0
            tr = {
                "tool": func["name"],
                "success": result.success,
                "data": result.data,
                "error": result.error,
            }
            if result.success:
                print(f"  ✅ 完成 ({elapsed:.1f}s)")
            else:
                print(f"  ❌ ({elapsed:.1f}s) {result.error[:80]}")
                error_logger.log_tool_error(func["name"], user_input, result.error, args)

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(tr, ensure_ascii=False),
            })

    return "⚠️ 达到最大工具调用轮数"
    ctx_mgr.add_pair(user_input, reply)
    return reply


def stream_reply(text: str, chat_llm: LLMClient, chat_prompt: str,
                 ctx_mgr: ContextManager, error_logger: ErrorLogger, last_reply: list) -> str:
    """流式输出回复"""
    messages = [{"role": "system", "content": chat_prompt}]
    messages.extend(ctx_mgr.get_messages())
    messages.append({"role": "user", "content": text})

    full = ""
    try:
        for chunk in chat_llm.stream(messages):
            print(chunk, end="", flush=True)
            full += chunk
    except Exception as e:
        error_logger.log_llm_error(context="stream", error_body=str(e))
        full = f"\n[流式中断: {e}]"
        print(full)

    print()
    if last_reply[0] and detect_correction(text):
        error_logger.log_ai_correction(text, last_reply[0])
    last_reply[0] = full
    ctx_mgr.add_pair(text, full)
    return full


def do_self_update(chat_llm: LLMClient, tool_llm: LLMClient,
                   chat_prompt: str, tool_prompt: str, tool_defs: list,
                   error_logger: ErrorLogger, version_mgr: VersionManager):
    """错误日志自我分析"""
    print("\n📦 检查版本归档...")
    try:
        version_mgr.ensure_v1_archived()
        print(f"✅ 当前版本: {version_mgr.get_current_version()}\n")
    except Exception as e:
        print(f"⚠️ 归档失败: {e}\n")

    print("📋 读取错误日志...")
    logs = error_logger.get_logs(100)
    stats = error_logger.get_stats()
    if logs:
        print(f"🔢 共 {stats['total']} 条日志")
        for t, count in stats["by_type"].items():
            print(f"  - {t}: {count}")
    else:
        print("✅ 没有错误日志")

    print("\n🧠 AI 分析中...\n")
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
        print(f"❌ 分析失败: {e}")
        return

    analysis_text = analysis_resp["choices"][0]["message"].get("content", "")
    print(f"📊 分析结果:\n{analysis_text[:1500]}\n")

    try:
        decision = _parse_decision(analysis_text)
    except Exception as e:
        error_logger.log_parse_error("self_update decision parse", str(e))
        print(f"⚠️ 解析失败: {e}")
        return

    if decision.get("action") != "update":
        print(f"💡 当前不需要更新\n理由: {decision.get('reasons', [])}")
        return

    print(f"🔧 修复文件: {decision.get('files_to_modify', [])}")
    print(f"📝 方案: {decision.get('implementation_plan', '')[:300]}...\n")

    print("💾 创建备份...")
    try:
        backup_path = version_mgr.backup_current()
        print(f"✅ 备份到: {backup_path}")
    except Exception as e:
        print(f"⚠️ 备份失败: {e}")
        backup_path = None

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

    print("⚙️ 工具AI执行修复...")
    try:
        fix_resp = tool_llm.chat([
            {"role": "system", "content": tool_prompt},
            {"role": "user", "content": exec_prompt + "\n\n必须使用 write 工具写入修改后的文件。"},
        ], tools=tool_defs)
    except Exception as e:
        error_logger.log_llm_error(context="self_update fix", error_body=str(e))
        print(f"❌ 修复失败: {e}")
        return

    fix_msg = fix_resp["choices"][0]["message"]
    if fix_msg.get("tool_calls"):
        print("🔧 写入修改:")
        for tc in fix_msg["tool_calls"]:
            func = tc["function"]
            args = json.loads(func["arguments"])
            print(f"  🔧 {func['name']}({json.dumps(args, ensure_ascii=False)[:150]})")
            result = execute_tool(func["name"], args)
            if result.success:
                print(f"  ✅ 完成")
            else:
                print(f"  ❌ 失败: {result.error}")
                error_logger.log_tool_error(func["name"], "self_update", result.error, args)
    else:
        print(f"💬 {fix_msg.get('content', '(无内容)')[:500]}")

    print("\n🧪 测试新版本...")
    ok, msg = version_mgr.test_version(BASE_DIR)
    if ok:
        next_version = version_mgr.get_next_version()
        version_mgr.create_version(next_version)
        version_mgr.switch_version(next_version)
        print(f"✅ {msg}")
        print(f"✅ 新版本: {next_version}")
        if backup_path:
            print(f"📂 备份: {backup_path}")
        print(f"⚠️ 请重启终端使更新生效\n")
    else:
        print(f"❌ 测试失败: {msg}")
        print("🔄 自动回滚...")
        if backup_path:
            try:
                version_mgr.restore_from_backup(backup_path)
                print("✅ 已回滚")
            except Exception as e:
                print(f"❌ 回滚失败: {e}")


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


def main():
    config = load_config()
    
    # 检查 API key
    api_key = config.get('chat_ai', {}).get('api_key', '')
    if not api_key:
        print("错误：未配置 API Key")
        print("")
        print("请通过以下方式之一配置：")
        print("")
        print("方式一：设置环境变量")
        print('  export DEEPSEEK_API_KEY="your_key"    # Linux/Mac')
        print('  set DEEPSEEK_API_KEY=your_key         # Windows CMD')
        print('  $env:DEEPSEEK_API_KEY="your_key"      # PowerShell')
        print("")
        print("方式二：运行交互式配置")
        print("  python main.py setup")
        print("")
        print("获取 API Key：https://platform.deepseek.com/api_keys")
        return
    
    chat_prompt = load_prompt("chat.txt")
    tool_prompt = load_prompt("tool.txt")
    tool_defs = get_tool_definitions()

    chat_llm = LLMClient(config["chat_ai"])
    tool_llm = LLMClient(config["tool_ai"])
    llm = {"chat": chat_llm, "tool": tool_llm}

    def swap_model(target: str, model: str):
        config_path = BASE_DIR / "config.yaml"
        if not config_path.exists():
            print("❌ 配置文件不存在")
            return
        raw = config_path.read_text(encoding="utf-8")
        data = yaml.safe_load(raw)
        if target in ("chat", "both"):
            data["chat_ai"]["model"] = model
        if target in ("tool", "both"):
            data["tool_ai"]["model"] = model
        config_path.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False), encoding="utf-8")
        if target in ("chat", "both"):
            llm["chat"] = LLMClient(data["chat_ai"])
            sanitizer.set_llm_client(llm["chat"])
        if target in ("tool", "both"):
            llm["tool"] = LLMClient(data["tool_ai"])
        print(f"✅ 已切换: {target} -> {model}")

    sanitizer.set_llm_client(llm["chat"])

    max_active = config.get("context", {}).get("max_active", 20)
    ctx_mgr = ContextManager(BASE_DIR, max_active=max_active)
    error_logger = ErrorLogger(BASE_DIR)
    version_mgr = VersionManager(BASE_DIR)
    last_reply = [""]

    print(f"""
╔══════════════════════════════════════╗
║        ⚡ AI Shell 终端版 v2         ║
║                                      ║
║  模型: {config['chat_ai']['model']:<24}║
║  版本: {version_mgr.get_current_version():<24}║
║  上下文: 最近 {ctx_mgr.max_active} 条活跃 + 本地归档   ║
║                                      ║
║  输入需求，AI自行判断执行            ║
║  \\ 续行  |  /model <name> 热切换大模型║
║  /self-update  错误日志自我分析      ║
║  /context      查看上下文统计        ║
║  /errors       查看错误日志           ║
║  /reload-tools 热加载创造空间工具    ║
║  /uninstall    卸载 AI Shell         ║
║  /quit         退出                   ║
╚══════════════════════════════════════╝
""")

    def read_multiline():
        lines = []
        first = True
        while True:
            try:
                prompt = "🧑 " if first else "... "
                line = input(prompt)
                first = False
                if not line:
                    if lines:
                        break
                    continue
                if line.endswith("\\"):
                    lines.append(line[:-1].rstrip())
                    continue
                lines.append(line)
                break
            except (EOFError, KeyboardInterrupt):
                return None
        return " ".join(lines)

    while True:
        try:
            user_input = read_multiline()
            if user_input is None:
                print("\n👋 再见！")
                break
            user_input = user_input.strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见！")
            break

        if not user_input:
            continue
        if user_input in ("/quit", "/exit", "/q"):
            print("👋 再见！")
            break

        if user_input == "/model":
            print(f"\n🔄 当前模型:")
            print(f"  对话 AI: {llm['chat'].model}")
            print(f"  工具 AI: {llm['tool'].model}")
            print(f"\n  可切换模型: deepseek-v4-flash, deepseek-v4-pro")
            print(f"  用法: /model chat <name>  |  /model tool <name>  |  /model both <name>")
            print()
            continue

        if user_input.startswith("/model "):
            parts = user_input.split()
            if len(parts) >= 3:
                target, model = parts[1], parts[2]
                if target in ("chat", "tool", "both"):
                    swap_model(target, model)
                    print(f"  当前: 对话={llm['chat'].model}  工具={llm['tool'].model}\n")
                else:
                    print(f"❌ 目标错误: {target}，应为 chat/tool/both\n")
            else:
                print("❌ 用法: /model chat|tool|both <model_name>\n")
            continue

        if user_input == "/self-update":
            do_self_update(llm["chat"], llm["tool"],
                          chat_prompt, tool_prompt, tool_defs,
                          error_logger, version_mgr)
            continue

        if user_input == "/context":
            stats = ctx_mgr.get_stats()
            print(f"\n📊 上下文统计:")
            print(f"  活跃消息: {stats['active']}/{stats['max_active']}")
            print(f"  归档消息: {stats['archived']}")
            print(f"  归档文件: {stats['archive_files']} 个")
            print()
            continue

        if user_input == "/errors":
            stats = error_logger.get_stats()
            print(f"\n📋 错误日志总览:")
            print(f"  总计: {stats['total']} 条")
            for t, count in stats["by_type"].items():
                print(f"  - {t}: {count}")
            recent = error_logger.get_logs(5)
            if recent:
                print(f"\n  最近 {len(recent)} 条:")
                for entry in recent:
                    print(f"    [{entry.get('type')}] {entry.get('error', entry.get('user_input', ''))[:60]}")
            print()
            continue

        if user_input == "/reload-tools":
            from tools import reload_tools
            result = reload_tools()
            print(f"\n🔄 工具热加载:")
            print(f"  加载前: {result['before']} 个工具")
            print(f"  加载后: {result['after']} 个工具")
            print(f"  新增: {result['loaded']} 个")
            print(f"  当前: {', '.join(result['tools'])}")
            print()
            continue

        if user_input == "/uninstall":
            from uninstall import interactive_uninstall
            interactive_uninstall()
            break

        print()

        sanitized_input = sanitizer.sanitize(user_input)

        # 正常对话
        check_messages = [
            {"role": "system", "content": chat_prompt},
            {"role": "user", "content": sanitized_input},
        ]
        try:
            check = llm["chat"].chat(check_messages, tools=tool_defs)
        except Exception as e:
            error_logger.log_llm_error(context="pre-check", error_body=str(e))
            print(f"🤖 ❌ AI 调用失败: {e}\n")
            continue

        need_tools = bool(check["choices"][0]["message"].get("tool_calls"))

        if need_tools:
            reply = do_chat(user_input, llm["chat"], llm["tool"],
                           chat_prompt, tool_prompt, tool_defs,
                           ctx_mgr, error_logger, last_reply)
            print(f"\n🤖 {reply}\n")
        else:
            print("🤖 ", end="", flush=True)
            reply = stream_reply(sanitized_input, llm["chat"], chat_prompt,
                                ctx_mgr, error_logger, last_reply)
            print()

    llm["chat"].close()
    llm["tool"].close()


if __name__ == "__main__":
    main()
