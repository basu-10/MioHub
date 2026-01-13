import os, requests
import config


class LLMClient:
    """LLM client with optional summarization configuration."""

    def __init__(self, provider=None, model=None, use_summarizer=False):
        # Allow callers to force summarizer mode (uses OpenRouter + summarization model)
        if use_summarizer:
            provider = "openrouter"
            model = getattr(config, "SUMMARIZATION_MODEL", config.DEFAULT_CHAT_MODEL)

        self.provider = (provider or config.PROVIDER).lower()
        self.model = model or config.DEFAULT_CHAT_MODEL
        self._configure_endpoint(self.provider)

    def _configure_endpoint(self, provider: str):
        """Set endpoint URL and headers for the selected provider."""
        if provider == "groq":
            self.url = "https://api.groq.com/openai/v1/chat/completions"
            api_key = config.GROQ_API_KEY
            # Log API key status for debugging (masked for security)
            key_preview = f"{api_key[:8]}...{api_key[-4:]}" if api_key and len(api_key) > 12 else "[MISSING OR INVALID]"
            print(f"[LLM CONFIG] provider=groq api_key={key_preview}", flush=True)
            self.headers = {"Authorization": f"Bearer {api_key}"}
        elif provider == "openrouter":
            self.url = "https://openrouter.ai/api/v1/chat/completions"
            openrouter_key = getattr(config, "OPENROUTER_API_KEY", "")
            or_site_url = getattr(config, "OR_SITE_URL", "http://localhost")
            or_app_name = getattr(config, "OR_APP_NAME", "Editor Utilities")
            self.headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "HTTP-Referer": or_site_url,
                "X-Title": or_app_name,
            }
        elif provider == "fireworks":
            self.url = "https://api.fireworks.ai/inference/v1/chat/completions"
            fireworks_key = getattr(config, "FIREWORKS_API_KEY", "")
            self.headers = {"Authorization": f"Bearer {fireworks_key}"}
        elif provider == "together":
            self.url = "https://api.together.xyz/v1/chat/completions"
            together_key = getattr(config, "TOGETHER_API_KEY", "")
            self.headers = {"Authorization": f"Bearer {together_key}"}
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def chat(self, messages, temperature=0.2, max_tokens=512, timeout=60, model=None):
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            # "stream": True,  # you can enable streaming later
        }
        r = requests.post(self.url, json=payload, headers=self.headers, timeout=timeout)
        r.raise_for_status()
        j = r.json()
        # OpenAI-compatible shape
        try:
            return j["choices"][0]["message"]["content"]
        except Exception:
            # Fallback best-effort
            return str(j)
