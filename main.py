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
import argparse


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
        interactive_setup()
        return

    # 检测是否需要首次配置
    from setup import run_setup_if_needed
    if not run_setup_if_needed():
        print("配置未完成，退出。")
        sys.exit(1)

    # 启动
    if args.mode is None or args.mode == "server":
        from config import load_config
        cfg = load_config()
        if args.host:
            cfg["server"]["host"] = args.host
        if args.port:
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
