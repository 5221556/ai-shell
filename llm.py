"""
llm.py - LLM 调用客户端（同步版）
"""

import json
import requests


class LLMClient:
    """同步 LLM 调用接口"""

    def __init__(self, config: dict):
        self.base_url = config["base_url"].rstrip("/")
        self.api_key = config.get("api_key", "")
        self.model = config["model"]
        self.temperature = config.get("temperature", 0.7)
        self.max_tokens = config.get("max_tokens", 2048)
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        if self.api_key:
            self.session.headers["Authorization"] = f"Bearer {self.api_key}"

    def chat(self, messages: list, tools: list = None) -> dict:
        """非流式调用"""
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            body["tools"] = tools

        resp = self.session.post(
            f"{self.base_url}/chat/completions",
            json=body,
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()

    def stream(self, messages: list, tools: list = None):
        """流式调用，yield 每个 token"""
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": True,
        }
        if tools:
            body["tools"] = tools

        resp = self.session.post(
            f"{self.base_url}/chat/completions",
            json=body,
            stream=True,
            timeout=120,
        )
        resp.raise_for_status()

        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            data = line[6:]
            if data.strip() == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                delta = chunk["choices"][0].get("delta", {})
                content = delta.get("content")
                if content:
                    yield content
            except (json.JSONDecodeError, KeyError, IndexError):
                continue

    def close(self):
        self.session.close()
