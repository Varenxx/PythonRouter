"""Клиент для обращения к локальной модели Ollama."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OllamaClient:
    """Отправляет запросы локальной модели Ollama."""

    def __init__(
        self,
        model: str = "qwen3.5:9b-q4_K_M",
        base_url: str = "http://127.0.0.1:11434",
        timeout: int = 120,
    ) -> None:
        self.model = model.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

        if not self.model:
            raise ValueError("Название модели не может быть пустым.")

        if self.timeout <= 0:
            raise ValueError("Тайм-аут должен быть положительным.")

    def chat(self, prompt: str) -> str:
        """Отправляет текстовый запрос и возвращает ответ модели."""

        normalized_prompt = prompt.strip()

        if not normalized_prompt:
            raise ValueError("Запрос к модели не может быть пустым.")

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": normalized_prompt,
                }
            ],
            "stream": False,
            "think": False,
            "options": {
                "temperature": 0,
                "num_ctx": 4096,
            },
        }

        request = Request(
            url=f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                response_data = json.loads(
                    response.read().decode("utf-8")
                )
        except HTTPError as exc:
            raise RuntimeError(
                f"Ollama вернула HTTP-ошибку {exc.code}."
            ) from exc
        except URLError as exc:
            raise RuntimeError(
                "Не удалось подключиться к Ollama. "
                "Проверь, запущена ли Ollama."
            ) from exc
        except TimeoutError as exc:
            raise RuntimeError(
                "Истекло время ожидания ответа Ollama."
            ) from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Ollama вернула ответ в неверном формате JSON."
            ) from exc

        message = response_data.get("message")

        if not isinstance(message, dict):
            raise RuntimeError(
                "В ответе Ollama отсутствует объект message."
            )

        content = message.get("content")

        if not isinstance(content, str) or not content.strip():
            raise RuntimeError(
                "Ollama вернула пустой текстовый ответ."
            )

        return content.strip()