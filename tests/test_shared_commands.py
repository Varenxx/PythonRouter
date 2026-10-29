"""Проверки команд через общий адаптер без реальной модели и SQLite."""

import unittest
from contextlib import ExitStack
from unittest.mock import Mock, call, patch

from router.bootstrap import create_router_adapter
from router.commands import handle_agent_command
from router.python_agent import ChatClient


class TestSharedCommands(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)

        for target in (
            "sqlite3.connect",
            "urllib.request.urlopen",
            "router.ollama_client.urlopen",
            "router.commands.execute_demo_task",
            "router.commands.execute_python_task",
            "router.commands.OllamaClient",
        ):
            blocker = self.stack.enter_context(
                patch(
                    target,
                    side_effect=AssertionError(
                        f"Запрещённый вызов в тесте общего адаптера: {target}"
                    ),
                )
            )
            self.addCleanup(blocker.assert_not_called)

        self.client = Mock(spec=ChatClient)
        self.client.chat.return_value = "Ответ Python-агента"
        self.adapter = create_router_adapter(self.client)

        self.execute = self.stack.enter_context(
            patch.object(
                self.adapter,
                "execute",
                wraps=self.adapter.execute,
            )
        )

    def test_demo_command_uses_shared_adapter_without_model(self):
        answer = handle_agent_command(
            "демо: Проверить общий маршрут.",
            router_adapter=self.adapter,
        )

        self.assertIn("Агент: demo_agent", answer)
        self.assertIn("Статус: completed", answer)
        self.assertIn("Проверить общий маршрут.", answer)
        self.execute.assert_called_once_with(
            description="Проверить общий маршрут.",
            required_capabilities=("demo",),
        )
        self.client.chat.assert_not_called()

    def test_python_command_preserves_code_and_uses_shared_adapter(self):
        description = (
            "Объясни код:\n"
            "def greet(name):\n"
            "    return f'Привет: {name}'"
        )

        answer = handle_agent_command(
            "  PYTHON:   " + description + "  ",
            router_adapter=self.adapter,
        )

        self.assertEqual(
            answer,
            "Агент: python_agent\n"
            "Статус: completed\n"
            "Результат: Ответ Python-агента",
        )
        self.execute.assert_called_once_with(
            description=description,
            required_capabilities=("python",),
        )
        self.client.chat.assert_called_once()
        self.assertIn(description, self.client.chat.call_args.args[0])

    def test_alternating_commands_use_same_adapter(self):
        prompts = (
            "демо: Первая демонстрация.",
            "python: Объясни enumerate.",
            "ДЕМО: Вторая демонстрация.",
        )

        answers = [
            handle_agent_command(prompt, router_adapter=self.adapter)
            for prompt in prompts
        ]

        self.assertIn("Агент: demo_agent", answers[0])
        self.assertIn("Агент: python_agent", answers[1])
        self.assertIn("Агент: demo_agent", answers[2])
        self.assertIn("Первая демонстрация.", answers[0])
        self.assertIn("Вторая демонстрация.", answers[2])

        for answer in answers:
            self.assertIn("Статус: completed", answer)

        self.assertEqual(
            self.execute.call_args_list,
            [
                call(
                    description="Первая демонстрация.",
                    required_capabilities=("demo",),
                ),
                call(
                    description="Объясни enumerate.",
                    required_capabilities=("python",),
                ),
                call(
                    description="Вторая демонстрация.",
                    required_capabilities=("demo",),
                ),
            ],
        )
        self.client.chat.assert_called_once()

    def test_empty_commands_do_not_reach_adapter(self):
        for prompt in (
            "демо:",
            " ДЕМО: \n\t ",
            "python:",
            " PYTHON: \n\t ",
        ):
            with self.subTest(prompt=prompt):
                answer = handle_agent_command(
                    prompt,
                    router_adapter=self.adapter,
                )
                self.assertIn("Ошибка:", answer)
                self.assertIn("необходимо указать описание задачи", answer)

        self.execute.assert_not_called()
        self.client.chat.assert_not_called()

    def test_other_input_does_not_reach_adapter(self):
        for prompt in (
            "Привет",
            "Объясни Python",
            "python",
            "pythonic: пример",
            "демонстрация: пример",
            "",
            None,
            123,
        ):
            with self.subTest(prompt=prompt):
                answer = handle_agent_command(
                    prompt,
                    router_adapter=self.adapter,
                )
                self.assertIsNone(answer)

        self.execute.assert_not_called()
        self.client.chat.assert_not_called()

    def test_model_failure_is_reported_and_later_commands_work(self):
        self.client.chat.side_effect = [
            RuntimeError("Тестовая ошибка модели."),
            "Ответ после восстановления.",
        ]

        failed = handle_agent_command(
            "python: Первая задача.",
            router_adapter=self.adapter,
        )
        demo = handle_agent_command(
            "демо: Проверка после ошибки.",
            router_adapter=self.adapter,
        )
        recovered = handle_agent_command(
            "python: Вторая задача.",
            router_adapter=self.adapter,
        )

        self.assertEqual(
            failed,
            "Ошибка выполнения: RuntimeError: Тестовая ошибка модели.",
        )
        self.assertIn("Агент: demo_agent", demo)
        self.assertIn("Статус: completed", demo)
        self.assertIn("Агент: python_agent", recovered)
        self.assertIn("Статус: completed", recovered)
        self.assertIn("Ответ после восстановления.", recovered)
        self.assertEqual(self.execute.call_count, 3)
        self.assertEqual(self.client.chat.call_count, 2)

    def test_conflicting_dependencies_are_rejected_before_execution(self):
        with self.assertRaisesRegex(
            ValueError,
            "Передайте либо router_adapter, либо python_client",
        ):
            handle_agent_command(
                "python: Объясни списки.",
                python_client=self.client,
                router_adapter=self.adapter,
            )

        self.execute.assert_not_called()
        self.client.chat.assert_not_called()


if __name__ == "__main__":
    unittest.main()