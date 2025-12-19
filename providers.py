import os, requests
import config

class LLMClient:
    def __init__(self):
        self.provider = config.PROVIDER.lower()
        self.model = config.DEFAULT_CHAT_MODEL
        # Endpoints + headers per provider
        if self.provider == "groq":
            self.url = "https://api.groq.com/openai/v1/chat/completions"
            self.headers = {"Authorization": f"Bearer {config.GROQ_API_KEY}"}
        elif self.provider == "openrouter":
            self.url = "https://openrouter.ai/api/v1/chat/completions"
            openrouter_key = getattr(config, 'OPENROUTER_API_KEY', '')
            or_site_url = getattr(config, 'OR_SITE_URL', 'http://localhost')
            or_app_name = getattr(config, 'OR_APP_NAME', 'Editor Utilities')
            self.headers = {
                "Authorization": f"Bearer {openrouter_key}",
                "HTTP-Referer": or_site_url,
                "X-Title": or_app_name
            }
        elif self.provider == "fireworks":
            self.url = "https://api.fireworks.ai/inference/v1/chat/completions"
            fireworks_key = getattr(config, 'FIREWORKS_API_KEY', '')
            self.headers = {"Authorization": f"Bearer {fireworks_key}"}
        elif self.provider == "together":
            self.url = "https://api.together.xyz/v1/chat/completions"
            together_key = getattr(config, 'TOGETHER_API_KEY', '')
            self.headers = {"Authorization": f"Bearer {together_key}"}
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def chat(self, messages, temperature=0.2, max_tokens=512):
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            # "stream": True,  # you can enable streaming later
        }
        r = requests.post(self.url, json=payload, headers=self.headers, timeout=60)
        r.raise_for_status()
        j = r.json()
        # OpenAI-compatible shape
        try:
            return j["choices"][0]["message"]["content"]
        except Exception:
            # Fallback best-effort
            return str(j)
