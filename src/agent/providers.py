from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


DEFAULT_PROVIDER = "groq"
DEFAULT_GROQ_MODEL = "llama-3.1-8b-instant"
DEFAULT_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"
DEFAULT_OLLAMA_MODEL = "llama3.1:8b-instruct-q4_0"
DEFAULT_OLLAMA_BASE_URL = "http://localhost:11434"

TOOL_DEFINITIONS = [
    {
        "name": "get_schema",
        "description": "Return the SQLite schema, business glossary, query rules, and common join paths.",
        "parameters": {
            "type": "object",
            "properties": {
                "include_samples": {
                    "type": "boolean",
                    "description": "Whether to include up to three sample rows per table/view.",
                }
            },
            "required": ["include_samples"],
            "additionalProperties": False,
        },
    },
    {
        "name": "run_sql_query",
        "description": "Execute a read-only SQLite SELECT/WITH query against the beef and lamb market database.",
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A safe read-only SQLite SELECT or WITH query.",
                },
                "row_limit": {
                    "type": "integer",
                    "description": "Maximum rows to return, between 1 and 500.",
                },
            },
            "required": ["sql", "row_limit"],
            "additionalProperties": False,
        },
    },
]


class ProviderError(RuntimeError):
    """Raised when the selected AI provider cannot complete a request."""


@dataclass
class ProviderToolCall:
    name: str
    arguments: dict[str, Any]
    call_id: str | None = None


@dataclass
class ProviderResponse:
    content: str
    tool_calls: list[ProviderToolCall]


@dataclass
class ToolOutput:
    name: str
    content: str
    call_id: str | None = None


class ProviderConversation(Protocol):
    def next(self, tool_outputs: list[ToolOutput] | None = None) -> ProviderResponse:
        ...


class AIProvider(Protocol):
    name: str
    model: str

    def start(self, system_prompt: str, question: str) -> ProviderConversation:
        ...

    def status(self) -> dict[str, Any]:
        ...


def parse_json_arguments(arguments: Any) -> dict[str, Any]:
    if isinstance(arguments, dict):
        return arguments
    if not arguments:
        return {}
    return json.loads(arguments)


def openai_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["parameters"],
            "strict": True,
        }
        for tool in TOOL_DEFINITIONS
    ]


def chat_completion_tools() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        for tool in TOOL_DEFINITIONS
    ]


def get_item_value(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


class OpenAIResponsesConversation:
    def __init__(self, client: Any, model: str, system_prompt: str, question: str):
        self.client = client
        self.model = model
        self.system_prompt = system_prompt
        self.previous_response_id: str | None = None
        self.pending_question = question

    def next(self, tool_outputs: list[ToolOutput] | None = None) -> ProviderResponse:
        if self.previous_response_id is None:
            response = self.client.responses.create(
                model=self.model,
                instructions=self.system_prompt,
                input=self.pending_question,
                tools=openai_tools(),
            )
        else:
            response = self.client.responses.create(
                model=self.model,
                previous_response_id=self.previous_response_id,
                input=[
                    {
                        "type": "function_call_output",
                        "call_id": output.call_id,
                        "output": output.content,
                    }
                    for output in tool_outputs or []
                ],
                tools=openai_tools(),
            )

        self.previous_response_id = response.id
        function_calls = [
            item
            for item in getattr(response, "output", [])
            if get_item_value(item, "type") == "function_call"
        ]
        return ProviderResponse(
            content=getattr(response, "output_text", "") or "",
            tool_calls=[
                ProviderToolCall(
                    name=get_item_value(call, "name"),
                    arguments=parse_json_arguments(get_item_value(call, "arguments")),
                    call_id=get_item_value(call, "call_id"),
                )
                for call in function_calls
            ],
        )


class OpenAIProvider:
    name = "openai"

    def __init__(self) -> None:
        self.model = os.getenv("AI_MODEL") or os.getenv("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
        self.api_key = os.getenv("OPENAI_API_KEY")

    def start(self, system_prompt: str, question: str) -> ProviderConversation:
        if not self.api_key:
            raise ProviderError("OPENAI_API_KEY is not set.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderError(
                "The openai Python package is not installed. Install project API dependencies first."
            ) from exc

        return OpenAIResponsesConversation(
            client=OpenAI(api_key=self.api_key),
            model=self.model,
            system_prompt=system_prompt,
            question=question,
        )

    def status(self) -> dict[str, Any]:
        configured = bool(self.api_key)
        return {
            "provider": self.name,
            "model": self.model,
            "configured": configured,
            "available": configured,
            "detail": "OPENAI_API_KEY is set." if configured else "OPENAI_API_KEY is not set.",
        }


class OpenAICompatibleChatConversation:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        system_prompt: str,
        question: str,
        provider_label: str,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.provider_label = provider_label
        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

    def next(self, tool_outputs: list[ToolOutput] | None = None) -> ProviderResponse:
        for output in tool_outputs or []:
            if not output.call_id:
                continue
            self.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": output.call_id,
                    "content": output.content,
                }
            )

        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": self.messages,
                    "tools": chat_completion_tools(),
                    "tool_choice": "auto",
                    "temperature": 1e-8,
                },
                timeout=120,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500]
            raise ProviderError(
                f"{self.provider_label} request failed with HTTP {exc.response.status_code}: {detail}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"{self.provider_label} request failed: {exc}") from exc

        payload = response.json()
        choices = payload.get("choices") or []
        message = choices[0].get("message") if choices else {}
        message = message or {}
        self.messages.append(message)

        tool_calls = []
        for call in message.get("tool_calls") or []:
            function_call = call.get("function") or {}
            tool_calls.append(
                ProviderToolCall(
                    name=function_call.get("name", ""),
                    arguments=parse_json_arguments(function_call.get("arguments")),
                    call_id=call.get("id"),
                )
            )

        return ProviderResponse(
            content=message.get("content") or "",
            tool_calls=tool_calls,
        )


class GroqProvider:
    name = "groq"

    def __init__(self) -> None:
        self.base_url = os.getenv("GROQ_BASE_URL", DEFAULT_GROQ_BASE_URL).rstrip("/")
        self.model = os.getenv("AI_MODEL") or os.getenv("GROQ_MODEL") or DEFAULT_GROQ_MODEL
        self.api_key = os.getenv("GROQ_API_KEY")

    def start(self, system_prompt: str, question: str) -> ProviderConversation:
        if not self.api_key:
            raise ProviderError("GROQ_API_KEY is not set.")
        return OpenAICompatibleChatConversation(
            base_url=self.base_url,
            api_key=self.api_key,
            model=self.model,
            system_prompt=system_prompt,
            question=question,
            provider_label="Groq",
        )

    def status(self) -> dict[str, Any]:
        configured = bool(self.api_key)
        available = configured
        detail = "GROQ_API_KEY is set." if configured else "GROQ_API_KEY is not set."

        if configured:
            try:
                response = httpx.get(
                    f"{self.base_url}/models",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=5,
                )
                response.raise_for_status()
                models = response.json().get("data") or []
                model_ids = {model.get("id") for model in models}
                available = self.model in model_ids if model_ids else True
                detail = (
                    "Groq is reachable and the configured model is available."
                    if available
                    else f"Groq is reachable, but {self.model} was not listed for this account."
                )
            except httpx.HTTPStatusError as exc:
                available = False
                detail = f"Groq returned HTTP {exc.response.status_code}: {exc.response.text[:240]}"
            except httpx.HTTPError as exc:
                available = False
                detail = f"Groq is not reachable at {self.base_url}: {exc}"

        return {
            "provider": self.name,
            "model": self.model,
            "base_url": self.base_url,
            "configured": configured,
            "available": available,
            "detail": detail,
        }


class OllamaConversation:
    def __init__(self, base_url: str, model: str, system_prompt: str, question: str):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]

    def next(self, tool_outputs: list[ToolOutput] | None = None) -> ProviderResponse:
        for output in tool_outputs or []:
            self.messages.append(
                {
                    "role": "tool",
                    "content": output.content,
                    "tool_name": output.name,
                }
            )

        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": self.messages,
                    "tools": chat_completion_tools(),
                    "stream": False,
                    "options": {"temperature": 0},
                },
                timeout=120,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderError(f"Ollama request failed: {exc}") from exc

        payload = response.json()
        message = payload.get("message") or {}
        self.messages.append(message)
        tool_calls = []
        for call in message.get("tool_calls") or []:
            function_call = call.get("function") or {}
            tool_calls.append(
                ProviderToolCall(
                    name=function_call.get("name", ""),
                    arguments=parse_json_arguments(function_call.get("arguments")),
                )
            )

        return ProviderResponse(
            content=message.get("content") or "",
            tool_calls=tool_calls,
        )


class OllamaProvider:
    name = "ollama"

    def __init__(self) -> None:
        self.base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL).rstrip("/")
        self.model = os.getenv("AI_MODEL") or os.getenv("OLLAMA_MODEL") or DEFAULT_OLLAMA_MODEL

    def start(self, system_prompt: str, question: str) -> ProviderConversation:
        return OllamaConversation(
            base_url=self.base_url,
            model=self.model,
            system_prompt=system_prompt,
            question=question,
        )

    def status(self) -> dict[str, Any]:
        try:
            response = httpx.get(f"{self.base_url}/api/tags", timeout=2)
            response.raise_for_status()
            models = response.json().get("models") or []
            installed_models = {model.get("name") for model in models}
            available = self.model in installed_models
            detail = (
                "Ollama is running and the configured model is installed."
                if available
                else f"Ollama is running, but {self.model} is not installed."
            )
        except httpx.HTTPError as exc:
            available = False
            detail = f"Ollama is not reachable at {self.base_url}: {exc}"

        return {
            "provider": self.name,
            "model": self.model,
            "base_url": self.base_url,
            "configured": True,
            "available": available,
            "detail": detail,
        }


def selected_provider_name() -> str:
    return os.getenv("AI_PROVIDER", DEFAULT_PROVIDER).strip().lower()


def create_provider() -> AIProvider:
    provider_name = selected_provider_name()
    if provider_name == "groq":
        return GroqProvider()
    if provider_name == "openai":
        return OpenAIProvider()
    if provider_name == "ollama":
        return OllamaProvider()
    raise ProviderError(
        f"Unsupported AI_PROVIDER '{provider_name}'. Use 'groq', 'ollama', or 'openai'."
    )
