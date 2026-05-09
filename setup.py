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
        "url": "https://api.deepseek.com",
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
        "name": "Claude (Anthropic)",
        "url": "https://api.anthropic.com/v1",
        "models": ["claude-3-5-sonnet-20241022", "claude-3-haiku-20240307"],
        "default": "claude-3-5-sonnet-20241022",
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
    """检查是否已有有效配置（API key 不为空）"""
    config_path = BASE_DIR / "config.yaml"
    if not config_path.exists():
        return False
    try:
        content = config_path.read_text(encoding="utf-8")
        return "api_key:" in content and 'api_key: ""' not in content and "api_key: ${" not in content
    except Exception:
        return False


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

    print()
    print("=" * 50)
    print(f"  配置已保存到: {config_path}")
    print(f"  服务商: {base_url}")
    print(f"  模型: {model}")
    print(f"  地址: http://{host}:{port}")
    print("=" * 50)
    print()

    return True
