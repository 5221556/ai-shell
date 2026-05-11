"""
setup.py - 首次运行交互式配置
"""

import sys
from pathlib import Path
from paths import BASE_DIR, RESOURCE_DIR


CONFIG_TEMPLATE = """server:
  host: "{host}"
  port: {port}

chat_ai:
  base_url: "{base_url}"
  api_key: "{api_key}"
  model: "{model}"
  temperature: 0.7
  max_tokens: 16384

tool_ai:
  base_url: "{base_url}"
  api_key: "{api_key}"
  model: "{model}"
  temperature: 0.1
  max_tokens: 65536

context:
  max_active: 20

self_update:
  max_log_entries: 100
  auto_backup: true
  test_timeout: 30

tools:
  read:
    allowed_dirs: ["/home", "/tmp", "."]
  write:
    allowed_dirs: ["/tmp", "./workspace"]
  exec:
    timeout: 30
"""

# 常见服务商配置
PROVIDERS = {
    "1": {
        "name": "DeepSeek",
        "url": "https://api.deepseek.com/v1",
        "models": ["deepseek-v4-flash", "deepseek-v4-pro"],
        "default": "deepseek-v4-flash",
    },
    "2": {
        "name": "OpenAI",
        "url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "default": "gpt-4o-mini",
    },
    "3": {
        "name": "Moonshot (月之暗面)",
        "url": "https://api.moonshot.cn/v1",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "default": "moonshot-v1-8k",
    },
    "4": {
        "name": "OpenRouter (聚合平台，支持Claude/Gemini等)",
        "url": "https://openrouter.ai/api/v1",
        "models": ["anthropic/claude-3.5-sonnet", "google/gemini-pro-1.5", "meta-llama/llama-3.1-405b-instruct"],
        "default": "anthropic/claude-3.5-sonnet",
    },
    "5": {
        "name": "通义千问 (阿里)",
        "url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-turbo", "qwen-plus", "qwen-max"],
        "default": "qwen-turbo",
    },
    "6": {
        "name": "GLM (智谱)",
        "url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4", "glm-4-flash", "glm-3-turbo"],
        "default": "glm-4-flash",
    },
    "7": {
        "name": "Ollama (本地)",
        "url": "http://localhost:11434/v1",
        "models": ["llama3", "qwen2", "deepseek-v2"],
        "default": "llama3",
    },
}


def _ask(prompt: str, default: str = "") -> str:
    """带默认值的输入"""
    hint = f" [{default}]" if default else ""
    val = input(f"{prompt}{hint}: ").strip()
    return val if val else default


def has_valid_config() -> bool:
    """检查是否已有有效配置（API key 不为空或环境变量已设置）"""
    import os
    
    # 检查环境变量
    if os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY"):
        return True
    
    # 检查配置文件
    config_path = BASE_DIR / "config.yaml"
    if not config_path.exists():
        return False
    try:
        content = config_path.read_text(encoding="utf-8")
        return "api_key:" in content and 'api_key: ""' not in content and "api_key: ${" not in content
    except Exception:
        return False


def run_setup_if_needed() -> bool:
    """如果需要，运行首次配置"""
    if has_valid_config():
        return True
    print("\n检测到首次运行，需要配置 API。\n")
    return interactive_setup()


def create_config_from_env():
    """从环境变量创建配置"""
    import os
    api_key = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("AI_SHELL_BASE_URL", "https://api.deepseek.com")
    model = os.environ.get("AI_SHELL_MODEL", "deepseek-v4-flash")
    host = os.environ.get("AI_SHELL_HOST", "127.0.0.1")
    port = int(os.environ.get("AI_SHELL_PORT", "18080"))

    config_content = CONFIG_TEMPLATE.format(
        host=host,
        port=port,
        base_url=base_url,
        api_key=api_key,
        model=model,
    )

    config_path = BASE_DIR / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config_content, encoding="utf-8")
    print(f"配置已从环境变量创建: {config_path}")


def interactive_setup() -> bool:
    """交互式首次配置，返回是否成功"""
    print()
    print("=" * 50)
    print("  AI Shell - 首次配置")
    print("=" * 50)
    print()
    print("AI Shell 需要一个大语言模型 API 来工作。")
    print("支持多种服务商，也可以自定义。")
    print()

    # 服务商选择
    print("选择服务商：")
    for key, provider in PROVIDERS.items():
        print(f"  {key}) {provider['name']}")
    print(f"  8) 其他（自定义地址）")
    print()

    choice = _ask("选择", "1")

    if choice in PROVIDERS:
        provider = PROVIDERS[choice]
        base_url = provider["url"]
        print(f"\n已选：{provider['name']} ({base_url})")
        print(f"\n可用模型：")
        for i, m in enumerate(provider["models"], 1):
            print(f"  {i}) {m}")
        model_choice = _ask("选择模型（输入序号或直接输入模型名）", "1")
        try:
            idx = int(model_choice) - 1
            if 0 <= idx < len(provider["models"]):
                default_model = provider["models"][idx]
            else:
                default_model = provider["default"]
        except ValueError:
            default_model = model_choice
    else:
        base_url = _ask("自定义 API 地址（OpenAI 兼容格式）")
        if not base_url:
            print("错误：API 地址不能为空。")
            return False
        default_model = _ask("模型名称", "deepseek-v4-flash")

    # API Key
    print()
    api_key = _ask("API Key")
    if not api_key:
        print("\n错误：API Key 不能为空。")
        return False

    # 模型名称确认
    model = _ask("模型名称确认", default_model)

    # Server settings
    print()
    host = _ask("Web 服务监听地址", "127.0.0.1")
    port_str = _ask("Web 服务端口", "18080")
    try:
        port = int(port_str)
    except ValueError:
        print(f"端口无效，使用默认 18080")
        port = 18080

    # 写入配置
    config_content = CONFIG_TEMPLATE.format(
        host=host,
        port=port,
        base_url=base_url,
        api_key=api_key,
        model=model,
    )

    config_path = BASE_DIR / "config.yaml"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(config_content, encoding="utf-8")

    # 创建 .env 文件（方便后续使用）
    env_path = BASE_DIR / ".env"
    env_content = f'DEEPSEEK_API_KEY="{api_key}"\n'
    env_path.write_text(env_content, encoding="utf-8")

    print()
    print("=" * 50)
    print("  配置完成！")
    print("=" * 50)
    print()
    print(f"  配置文件: {config_path}")
    print(f"  环境文件: {env_path}")
    print()
    print("  服务商:", base_url)
    print("  模型:", model)
    print("  地址:", f"http://{host}:{port}")
    print()
    print("=" * 50)
    print()
    print("建议设置环境变量（永久生效）：")
    print()
    
    import platform
    system = platform.system()
    if system == "Windows":
        print(f'  setx DEEPSEEK_API_KEY "{api_key}"')
    elif system == "Darwin":
        print(f'  export DEEPSEEK_API_KEY="{api_key}"')
        print(f'  # 添加到 ~/.zshrc 或 ~/.bashrc 永久生效')
    else:
        print(f'  export DEEPSEEK_API_KEY="{api_key}"')
        print(f'  # 添加到 ~/.bashrc 或 ~/.zshrc 永久生效')
    
    print()
    print("或加载 .env 文件：")
    print(f'  source .env          # Linux/Mac')
    print(f'  Get-Content .env     # PowerShell (查看)')
    print()
    
    # 选择启动方式
    print("=" * 50)
    print("  选择启动方式")
    print("=" * 50)
    print()
    print("  1) Web 服务（浏览器访问）")
    print("  2) 终端版（命令行交互，推荐）")
    print("  3) 不启动，稍后手动运行")
    print()
    
    start_choice = _ask("选择", "2")
    
    if start_choice == "1":
        print("\n正在启动 Web 服务...")
        print(f"浏览器将自动打开 http://{host}:{port}")
        print("按 Ctrl+C 停止服务\n")
        return "web"
    elif start_choice == "2":
        print("\n正在启动终端版...\n")
        return "shell"
    else:
        print("\n配置完成！稍后可手动启动：")
        print("  ai-shell.exe           # 终端版（默认）")
        print("  ai-shell.exe server    # Web 服务")
        print()
        return "none"
