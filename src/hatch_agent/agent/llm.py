"""Small LLM client abstraction with provider registry.

This module provides a tiny, test-friendly abstraction for choosing and
invoking LLM providers based on configuration. Real providers (OpenAI/AWS)
can be plugged in later; a `mock` provider is included for local testing.

Implemented providers:
- MockProvider: local deterministic response
- OpenAIProvider: uses the `openai` package
- AzureOpenAIProvider: uses `openai` but configured for Azure OpenAI
- AWSProvider: uses `boto3` to call Bedrock or SageMaker runtimes
- GitHubProvider: lightweight wrapper that uses `requests` (placeholder)

All external SDK imports are performed lazily and raise descriptive
ProviderError messages if not installed.
"""
from typing import Dict, Any
from dataclasses import dataclass
import json


class ProviderError(RuntimeError):
    pass


class BaseProvider:
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config

    def complete(self, prompt: str) -> str:
        raise NotImplementedError

    def chat(self, message: str) -> str:
        # By default, route to complete
        return self.complete(message)


class MockProvider(BaseProvider):
    def complete(self, prompt: str) -> str:
        return f"[mock response] {prompt[:200]}"


class OpenAIProvider(BaseProvider):
    """Provider using the official openai Python package.

    Config keys supported:
    - api_key: optional (if not set, relies on env OPENAI_API_KEY)
    - model: model name to use
    """

    def _ensure_openai(self):
        try:
            import openai
            return openai
        except Exception as exc:  # pragma: no cover - environment dependent
            raise ProviderError("Install the 'openai' package to use the OpenAI provider (pip install openai)") from exc

    def complete(self, prompt: str) -> str:
        openai = self._ensure_openai()
        cfg_model = self.config.get("model")
        api_key = self.config.get("api_key")
        if api_key:
            openai.api_key = api_key
        model = cfg_model or self.config.get("model") or "gpt-3.5-turbo"
        # Try chat completion first (recommended)
        try:
            resp = openai.ChatCompletion.create(model=model, messages=[{"role": "user", "content": prompt}])
            # Response shape: choices[0].message.content
            return resp.choices[0].message.content
        except AttributeError:
            # Fallback to legacy Completion
            resp = openai.Completion.create(model=model, prompt=prompt, max_tokens=512)
            return resp.choices[0].text


class AzureOpenAIProvider(OpenAIProvider):
    """Azure OpenAI provider that configures the `openai` package for Azure.

    Config keys:
    - api_key, api_base, api_type ('azure'), api_version, deployment
    """

    def complete(self, prompt: str) -> str:
        openai = self._ensure_openai()
        api_key = self.config.get("api_key")
        api_base = self.config.get("api_base")
        api_type = self.config.get("api_type", "azure")
        api_version = self.config.get("api_version")
        deployment = self.config.get("deployment")  # deployment name (model alias)

        if api_key:
            openai.api_key = api_key
        if api_base:
            openai.api_base = api_base
        if api_type:
            openai.api_type = api_type
        if api_version:
            openai.api_version = api_version

        model = deployment or self.config.get("model")
        if not model:
            raise ProviderError("Azure provider requires 'deployment' or 'model' in configuration")

        # Use ChatCompletion for Azure; model argument is deployment name
        resp = openai.ChatCompletion.create(engine=model, messages=[{"role": "user", "content": prompt}])
        return resp.choices[0].message.content


class AWSProvider(BaseProvider):
    """AWS provider supporting Bedrock and SageMaker runtime calls.

    Config keys:
    - client: 'bedrock' (default) or 'sagemaker'
    - region, access_key, secret_key (optional; can rely on env/instance profile)
    - model: for bedrock use modelId; for sagemaker use endpoint name
    """

    def _get_boto3_client(self, service_name: str):
        try:
            import boto3
        except Exception as exc:  # pragma: no cover - environment dependent
            raise ProviderError("Install 'boto3' to use the AWS provider (pip install boto3)") from exc

        kwargs = {}
        if self.config.get("region"):
            kwargs["region_name"] = self.config.get("region")
        if self.config.get("access_key") and self.config.get("secret_key"):
            kwargs.update({
                "aws_access_key_id": self.config.get("access_key"),
                "aws_secret_access_key": self.config.get("secret_key"),
            })
        return boto3.client(service_name, **kwargs)

    def complete(self, prompt: str) -> str:
        client_type = self.config.get("client", "bedrock")
        model = self.config.get("model")
        if client_type == "bedrock":
            client = self._get_boto3_client("bedrock-runtime")
            # Bedrock expects a JSON-like input; many runtimes accept a body with "inputText"
            body = json.dumps({"input": prompt})
            try:
                resp = client.invoke_model(modelId=model, contentType="application/json", accept="application/json", body=body)
                # The response body can be a streaming or binary blob; try to parse
                if isinstance(resp.get("body"), (bytes, bytearray)):
                    text = resp.get("body").decode("utf-8")
                else:
                    text = resp.get("body")
                # Try to extract text field from JSON
                try:
                    parsed = json.loads(text)
                    return parsed.get("output", parsed.get("results", text))
                except Exception:
                    return str(text)
            except Exception as exc:
                raise ProviderError(f"AWS Bedrock invocation failed: {exc}") from exc
        elif client_type == "sagemaker":
            client = self._get_boto3_client("sagemaker-runtime")
            try:
                resp = client.invoke_endpoint(EndpointName=model, ContentType="text/plain", Body=prompt)
                body = resp.get("Body")
                if hasattr(body, "read"):
                    result = body.read().decode("utf-8")
                else:
                    result = str(body)
                return result
            except Exception as exc:
                raise ProviderError(f"SageMaker invocation failed: {exc}") from exc
        else:
            raise ProviderError(f"Unknown AWS client type: {client_type}")


class GitHubProvider(BaseProvider):
    """A lightweight GitHub-backed provider wrapper (placeholder).

    This class demonstrates how a GitHub-hosted model/endpoint could be wired
    but does not implement a real production integration. It requires `requests`.
    """

    def _ensure_requests(self):
        try:
            import requests
            return requests
        except Exception as exc:  # pragma: no cover - environment dependent
            raise ProviderError("Install 'requests' to use the GitHub provider (pip install requests)") from exc

    def complete(self, prompt: str) -> str:
        requests = self._ensure_requests()
        token = self.config.get("token")
        api = self.config.get("api", "https://api.github.com")
        endpoint = self.config.get("endpoint", "/gists")
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"token {token}"
        # As a placeholder we POST the prompt to an endpoint if configured
        url = api.rstrip("/") + "/" + endpoint.lstrip("/")
        try:
            resp = requests.post(url, json={"prompt": prompt}, headers=headers, timeout=10)
            resp.raise_for_status()
            try:
                data = resp.json()
                return str(data)
            except Exception:
                return resp.text
        except Exception as exc:
            raise ProviderError(f"GitHub provider request failed: {exc}") from exc


class ProviderRegistry:
    _providers = {
        "mock": MockProvider,
        "openai": OpenAIProvider,
        "azure": AzureOpenAIProvider,
        "aws": AWSProvider,
        "github": GitHubProvider,
    }

    @classmethod
    def get(cls, name: str, config: Dict[str, Any]) -> BaseProvider:
        pcls = cls._providers.get(name)
        if not pcls:
            raise ProviderError(f"Unknown provider: {name}")
        return pcls(config)


@dataclass
class LLMClient:
    provider_name: str
    model: str
    provider_config: Dict[str, Any]

    @classmethod
    def from_config(cls, cfg: Dict[str, Any]) -> "LLMClient":
        provider = cfg.get("provider", "mock")
        model = cfg.get("model", "gpt-sim-1")
        provider_cfg = cfg.get("providers", {}).get(provider, {})
        # Ensure the model is present in provider config for some providers
        if provider_cfg and "model" not in provider_cfg and model:
            provider_cfg = dict(provider_cfg)
            provider_cfg["model"] = model
        return cls(provider_name=provider, model=model, provider_config=provider_cfg)

    def _provider(self) -> BaseProvider:
        return ProviderRegistry.get(self.provider_name, self.provider_config)

    def complete(self, prompt: str) -> str:
        prov = self._provider()
        return prov.complete(prompt)

    def chat(self, message: str) -> str:
        prov = self._provider()
        return prov.chat(message)
