"""Тесты обработки явных команд агентов PythonRouter."""

import unittest

from router.commands import handle_agent_command


class TestAgentCommands(unittest.TestCase):

    def test_demo_command(self):
        result = handle_agent_command(
            "демо: Проверить маршрутизацию"
        )

        self.assertIsInstance(result, str)
        self.assertIn("Агент: demo_agent", result)
        self.assertIn("Статус: completed", result)

    def test_uppercase_demo_command(self):
        result = handle_agent_command(
            "ДЕМО: Проверить агента"
        )

        self.assertIn("Агент: demo_agent", result)

    def test_result_contains_description(self):
        result = handle_agent_command(
            "демо: Уникальная тестовая задача"
        )

        self.assertIn("Уникальная тестовая задача", result)

    def test_empty_description(self):
        result = handle_agent_command("демо:")

        self.assertIn("Ошибка:", result)

    def test_whitespace_description(self):
        result = handle_agent_command("демо:   ")

        self.assertIn("Ошибка:", result)

    def test_regular_message(self):
        result = handle_agent_command("Привет")

        self.assertIsNone(result)

    def test_similar_command_not_matched(self):
        result = handle_agent_command(
            "демонстрация: Проверить"
        )

        self.assertIsNone(result)

    def test_invalid_input_type(self):
        result = handle_agent_command(None)

        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
