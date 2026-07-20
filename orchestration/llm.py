"""LLM client wrapper.

在 Anthropic SDK 之上的一层薄缝：agent 依赖稳定的 `complete()` 签名，而非 SDK。
MockLLM 让整条 pipeline 可离线运行（测试/CI），无需 API key。
"""
from __future__ import annotations

import os
from typing import Callable, Dict, List, Optional, Protocol

from . import config


class LLMClient(Protocol):
    def complete(self, *, model: str, system: str, prompt: str, max_tokens: int = ...) -> str: ...


class AnthropicLLM:
    """真实客户端。SDK 延迟导入，使离线/测试路径无需安装 anthropic。"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        from anthropic import Anthropic

        kwargs: dict = {}
        base_url = base_url or config.get_base_url()
        if base_url:
            kwargs["base_url"] = base_url
        kwargs["max_retries"] = config.LLM_MAX_RETRIES
        kwargs["timeout"] = config.LLM_TIMEOUT_SECONDS
        # Bearer token（Anthropic 兼容网关，如 GLM）优先；否则用 x-api-key。
        auth_token = os.environ.get(config.AUTH_TOKEN_ENV)
        if auth_token and not api_key:
            kwargs["auth_token"] = auth_token
        else:
            kwargs["api_key"] = api_key or os.environ.get(config.API_KEY_ENV)
        self._client = Anthropic(**kwargs)

    def complete(
        self, *, model: str, system: str, prompt: str, max_tokens: int = config.MAX_TOKENS
    ) -> str:
        resp = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )


class MockLLM:
    """离线测试用。按 system prompt 里的标记子串匹配预设响应；记录调用便于断言。

    responses: {marker_substring: json_string}，例如 {"[agent:planner]": "{...}"}。
    handler:   可选，签名 (model, system, prompt) -> str，优先于 responses。
    """

    def __init__(
        self,
        responses: Optional[Dict[str, str]] = None,
        handler: Optional[Callable[[str, str, str], str]] = None,
    ):
        self.responses = responses or {}
        self.handler = handler
        self.calls: List[dict] = []

    def complete(
        self, *, model: str, system: str, prompt: str, max_tokens: int = config.MAX_TOKENS
    ) -> str:
        self.calls.append(
            {"model": model, "system": system, "prompt": prompt, "max_tokens": max_tokens}
        )
        if self.handler is not None:
            return self.handler(model, system, prompt)
        for marker, value in self.responses.items():
            if marker in system:
                return value
        return "{}"
