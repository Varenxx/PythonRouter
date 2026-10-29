"""Отдельный тест реального подключения к Ollama."""

import os
import unittest

from router.ollama_client import OllamaClient


@unittest.skipUnless(
    os.environ.get("RUN_OLLAMA_LIVE") == "1",
    "Для реального теста установи RUN_OLLAMA_LIVE=1",
)
class TestOllamaLive(unittest.TestCase):

    def test_model_returns_answer(self):
        client = OllamaClient(
            model="qwen3.5:9b-q4_K_M",
            timeout=120,
        )

        answer = client.chat(
            "Сколько будет 2 + 2? Ответь коротко."
        )

        self.assertIsInstance(answer, str)
        self.assertTrue(answer.strip())
        self.assertIn("4", answer)


if __name__ == "__main__":
    unittest.main()