"""
AI Shell v2 — 统一入口
用法:
  python main.py              启动 Web 服务（默认）
  python main.py server       启动 Web 服务
  python main.py shell        启动终端版
  python main.py setup        重新配置
  python main.py --help       帮助
"""

import sys
import os
import argparse


def is_interactive():
    """检测是否在交互式终端中运行"""
    return sys.stdin.isatty() and sys.stdout.isatty()


def main():
    parser = argparse.ArgumentParser(
        description="AI Shell v2 — 会写字就会编程",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  ai-shell.exe                  启动 Web 服务
  ai-shell.exe server --port 9000   指定端口
  ai-shell.exe shell            启动终端版
  ai-shell.exe setup            重新配置 API
        """,
    )
    sub = parser.add_subparsers(dest="mode")

    # server 子命令
    sp_server = sub.add_parser("server", help="启动 Web 服务")
    sp_server.add_argument("--host", default=None, help="监听地址")
    sp_server.add_argument("--port", type=int, default=None, help="监听端口")

    # shell 子命令
    sub.add_parser("shell", help="启动终端版")

    # setup 子命令
    sub.add_parser("setup", help="重新配置 API")

    args = parser.parse_args()

    # 强制 setup
    if args.mode == "setup":
        from setup import interactive_setup
        if not is_interactive():
            print("错误：setup 需要在终端中运行")
            print("请在命令行中执行：ai-shell.exe setup")
            sys.exit(1)
        interactive_setup()
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
            if not interactive_setup():
                print("配置未完成，退出。")
                sys.exit(1)
        else:
            # 非交互式，提示用户
            print("错误：未找到配置文件")
            print("")
            print("请先运行 setup 配置 API：")
            print("  1. 打开命令行（cmd/PowerShell）")
            print("  2. 执行：ai-shell.exe setup")
            print("")
            print("或设置环境变量：")
            print("  set DEEPSEEK_API_KEY=your_key")
            print("  ai-shell.exe")
            sys.exit(1)

    # 启动
    if args.mode is None or args.mode == "server":
        from config import load_config
        cfg = load_config()
        
        # 检查 API key
        api_key = cfg.get('chat_ai', {}).get('api_key', '')
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
            sys.exit(1)
        
        if hasattr(args, 'host') and args.host:
            cfg["server"]["host"] = args.host
        if hasattr(args, 'port') and args.port:
            cfg["server"]["port"] = args.port

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
