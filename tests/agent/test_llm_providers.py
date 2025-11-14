"""Pytest-based unit tests for LLM providers using module injection.

These tests use pytest's `monkeypatch` to inject fake SDK modules into
`sys.modules`, so tests run without external dependencies or network.
"""
import sys
import types
import json
import pytest
from hatch_agent.agent.llm import LLMClient, ProviderError


class FakeResponse:
    def __init__(self, content):
        self.choices = [types.SimpleNamespace(message=types.SimpleNamespace(content=content))]
        self.text = content


def test_mock_provider():
    cfg = {"provider": "mock", "model": "gpt-sim-1"}
    client = LLMClient.from_config(cfg)
    out = client.complete("hello")
    assert out.startswith("[mock response]")


def test_openai_provider_chat(monkeypatch):
    fake_openai = types.SimpleNamespace()

    def chat_create(model=None, messages=None):
        return FakeResponse("reply-from-openai-chat")

    fake_openai.ChatCompletion = types.SimpleNamespace(create=chat_create)
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    cfg = {"provider": "openai", "model": "gpt-3.5-turbo"}
    client = LLMClient.from_config(cfg)
    out = client.complete("hi")
    assert "reply-from-openai-chat" in out


def test_openai_provider_legacy(monkeypatch):
    fake_openai = types.SimpleNamespace()

    def completion_create(model=None, prompt=None, max_tokens=None):
        return types.SimpleNamespace(choices=[types.SimpleNamespace(text="legacy-response")])

    fake_openai.Completion = types.SimpleNamespace(create=completion_create)
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    cfg = {"provider": "openai", "model": "davinci"}
    client = LLMClient.from_config(cfg)
    out = client.complete("legacy test")
    assert "legacy-response" in out


def test_azure_provider(monkeypatch):
    fake_openai = types.SimpleNamespace()

    def chat_create(engine=None, messages=None):
        return FakeResponse("azure-reply")

    fake_openai.ChatCompletion = types.SimpleNamespace(create=chat_create)
    monkeypatch.setitem(sys.modules, "openai", fake_openai)

    cfg = {"provider": "azure", "providers": {"azure": {"deployment": "dep1"}}, "model": "gpt-azure"}
    client = LLMClient.from_config(cfg)
    out = client.complete("hello azure")
    assert "azure-reply" in out


def test_aws_bedrock_provider(monkeypatch):
    fake_boto3 = types.SimpleNamespace()

    class FakeClient:
        def invoke_model(self, modelId=None, contentType=None, accept=None, body=None):
            return {"body": b'{"output": "bedrock-good"}'}

    def boto3_client(name, **kwargs):
        return FakeClient()

    fake_boto3.client = boto3_client
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

    cfg = {"provider": "aws", "providers": {"aws": {"client": "bedrock", "model": "mymodel"}}}
    client = LLMClient.from_config(cfg)
    out = client.complete("hello")
    assert "bedrock-good" in out


def test_aws_sagemaker_provider(monkeypatch):
    fake_boto3 = types.SimpleNamespace()

    class FakeBody:
        def read(self):
            return b"sagemaker-good"

    class FakeClient:
        def invoke_endpoint(self, EndpointName=None, ContentType=None, Body=None):
            return {"Body": FakeBody()}

    def boto3_client(name, **kwargs):
        return FakeClient()

    fake_boto3.client = boto3_client
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

    cfg = {"provider": "aws", "providers": {"aws": {"client": "sagemaker", "model": "endpoint"}}}
    client = LLMClient.from_config(cfg)
    out = client.complete("hi")
    assert "sagemaker-good" in out


def test_github_provider(monkeypatch):
    fake_requests = types.SimpleNamespace()

    class FakeResp:
        def __init__(self):
            self._json = {"result": "ok"}
            self.text = "ok-text"

        def raise_for_status(self):
            return None

        def json(self):
            return self._json

    def post(url, json=None, headers=None, timeout=None):
        return FakeResp()

    fake_requests.post = post
    monkeypatch.setitem(sys.modules, "requests", fake_requests)

    cfg = {"provider": "github", "providers": {"github": {"endpoint": "/gists"}}}
    client = LLMClient.from_config(cfg)
    out = client.complete("hello")
    assert "ok" in out
