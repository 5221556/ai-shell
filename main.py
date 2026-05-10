"""
AI Shell v2 — 统一入口
用法:
  python main.py              启动 Web 服务（默认）
  python main.py server       启动 Web 服务
  python main.py shell        终端版
  python main.py setup        重新配置
  python main.py uninstall    卸载
  python main.py --help       帮助

双击 exe 自动启动服务并打开浏览器
"""

import sys
import os
import argparse
import threading
import webbrowser


def is_interactive():
    """检测是否在交互式终端中运行"""
    return sys.stdin.isatty() and sys.stdout.isatty()


def open_browser(host, port, delay=1.5):
    """延迟打开浏览器"""
    def _open():
        import time
        time.sleep(delay)
        webbrowser.open(f"http://{host}:{port}")
    thread = threading.Thread(target=_open, daemon=True)
    thread.start()


def show_error(title, message):
    """显示错误消息（支持 GUI 和终端）"""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, message, title, 0x10)
    except Exception:
        print(f"\n{title}")
        print(message)


def main():
    parser = argparse.ArgumentParser(
        description="AI Shell v2 — 会写字就会编程",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  ai-shell.exe                  启动 Web 服务
  ai-shell.exe server --port 9000   指定端口
  ai-shell.exe shell            终端版
  ai-shell.exe setup            重新配置 API
  ai-shell.exe uninstall        卸载
        """,
    )
    sub = parser.add_subparsers(dest="mode")

    # server 子命令
    sp_server = sub.add_parser("server", help="启动 Web 服务")
    sp_server.add_argument("--host", default=None, help="监听地址")
    sp_server.add_argument("--port", type=int, default=None, help="监听端口")

    # shell 子命令
    sub.add_parser("shell", help="终端版")

    # setup 子命令
    sub.add_parser("setup", help="重新配置 API")

    # uninstall 子命令
    sub.add_parser("uninstall", help="卸载 AI Shell")

    args = parser.parse_args()

    # 强制 setup
    if args.mode == "setup":
        from setup import interactive_setup
        if not is_interactive():
            show_error("AI Shell", "请在命令行中执行：ai-shell.exe setup")
            sys.exit(1)
        interactive_setup()
        return

    # 卸载
    if args.mode == "uninstall":
        from uninstall import interactive_uninstall
        if not is_interactive():
            show_error("AI Shell", "请在命令行中执行：ai-shell.exe uninstall")
            sys.exit(1)
        interactive_uninstall()
        return

    # 检测是否需要首次配置
    from setup import has_valid_config
    if not has_valid_config():
        # 检查环境变量
        api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if api_key:
            # 从环境变量创建配置
            from setup import create_config_from_env
            create_config_from_env()
        elif is_interactive():
            # 交互式终端，运行 setup
            print("\n检测到首次运行，需要配置 API。\n")
            from setup import interactive_setup
            result = interactive_setup()
            if not result:
                print("配置未完成，退出。")
                sys.exit(1)
            
            # 根据用户选择启动
            if result == "web":
                # 启动 Web 服务
                from config import load_config
                cfg = load_config()
                import server
                server.config = cfg
                server.main()
                return
            elif result == "shell":
                # 启动终端版
                import shell
                shell.main()
                return
            else:
                # 不启动
                return
        else:
            # 非交互式（双击 exe），显示错误
            show_error(
                "AI Shell - 首次配置",
                "首次运行需要配置 API Key。\n\n"
                "请先在命令行中执行：\n"
                "  ai-shell.exe setup\n\n"
                "或设置环境变量 DEEPSEEK_API_KEY"
            )
            sys.exit(1)

    # 启动
    if args.mode is None or args.mode == "server":
        from config import load_config
        cfg = load_config()
        
        # 检查 API key
        api_key = cfg.get('chat_ai', {}).get('api_key', '')
        if not api_key:
            if is_interactive():
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
            else:
                show_error(
                    "AI Shell - 配置错误",
                    "API Key 未配置。\n\n"
                    "请在命令行中执行：\n"
                    "  ai-shell.exe setup\n\n"
                    "或设置环境变量 DEEPSEEK_API_KEY"
                )
            sys.exit(1)
        
        if hasattr(args, 'host') and args.host:
            cfg["server"]["host"] = args.host
        if hasattr(args, 'port') and args.port:
            cfg["server"]["port"] = args.port

        # 双击 exe 时自动打开浏览器
        if not is_interactive():
            host = cfg["server"]["host"]
            port = cfg["server"]["port"]
            open_browser(host, port)

        import server
        server.config = cfg
        server.main()

    elif args.mode == "shell":
        import shell
        shell.main()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

