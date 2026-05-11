"""配置加载，支持环境变量替换"""
import os
import re
import yaml
from paths import BASE_DIR, RESOURCE_DIR


def load_config(path: str = None) -> dict:
    if path is not None:
        return _load_from(path)

    # 优先读取用户目录的配置（setup 生成的）
    user_config = BASE_DIR / "config.yaml"
    if user_config.exists():
        return _load_from(user_config)

    # 回退到内置默认配置
    return _load_from(RESOURCE_DIR / "config.yaml")


def _load_from(path) -> dict:
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    def replace_env(match):
        var = match.group(1)
        return os.environ.get(var, "")

    raw = re.sub(r'\$\{(\w+)\}', replace_env, raw)
    cfg = yaml.safe_load(raw)
    _fix_base_url(cfg)
    return cfg


def _fix_base_url(cfg: dict):
    for section in ("chat_ai", "tool_ai"):
        url = cfg.get(section, {}).get("base_url", "")
        if "api.deepseek.com" in url and not url.endswith("/v1"):
            cfg[section]["base_url"] = url.rstrip("/") + "/v1"
