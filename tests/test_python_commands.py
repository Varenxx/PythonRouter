"""Проверки команды python: без реальной модели и рабочей SQLite."""

import importlib
import io
import unittest
from contextlib import ExitStack, redirect_stdout
from unittest.mock import Mock, call, patch

from router.commands import handle_agent_command
from router.python_agent import ChatClient


class TestPythonCommands(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)

        for target in (
            "sqlite3.connect",
            "urllib.request.urlopen",
            "router.ollama_client.urlopen",
        ):
            blocker = self.stack.enter_context(
                patch(
                    target,
                    side_effect=AssertionError(
                        f"Внешнее обращение запрещено: {target}"
                    ),
                )
            )
            self.addCleanup(blocker.assert_not_called)

        self.client = Mock(spec=ChatClient)
        self.client.chat.return_value = "Тестовый ответ Python-агента"

        self.client_factory = self.stack.enter_context(
            patch(
                "router.commands.OllamaClient",
                autospec=True,
                return_value=self.client,
            )
        )

    def test_python_command_uses_explicit_client(self):
        answer = handle_agent_command(
            "python: Объясни списки.",
            python_client=self.client,
        )

        self.assertEqual(
            answer,
            "Агент: python_agent\n"
            "Статус: completed\n"
            "Результат: Тестовый ответ Python-агента",
        )
        self.client.chat.assert_called_once()
        self.assertIn(
            "Объясни списки.",
            self.client.chat.call_args.args[0],
        )
        self.client_factory.assert_not_called()

    def test_command_preserves_code_colons_and_accepts_uppercase(self):
        description = (
            "Объясни код:\n"
            "def greet(name):\n"
            "    return f'Привет: {name}'"
        )

        answer = handle_agent_command(
            "  PYTHON:   " + description + "  ",
            python_client=self.client,
        )

        self.assertIn("Статус: completed", answer)
        self.client.chat.assert_called_once()
        self.assertIn(description, self.client.chat.call_args.args[0])
        self.client_factory.assert_not_called()

    def test_empty_python_command_does_not_create_or_call_client(self):
        for prompt in ("python:", " PYTHON: \n\t "):
            with self.subTest(prompt=prompt):
                answer = handle_agent_command(prompt)

                self.assertEqual(
                    answer,
                    "Ошибка: после команды 'python:' "
                    "необходимо указать описание задачи.",
                )

        self.client_factory.assert_not_called()
        self.client.chat.assert_not_called()

    def test_other_messages_do_not_create_or_call_client(self):
        for prompt in (
            "Привет",
            "Объясни Python",
            "python",
            "pythonic: пример",
            "",
            None,
            123,
        ):
            with self.subTest(prompt=prompt):
                self.assertIsNone(handle_agent_command(prompt))

        self.client_factory.assert_not_called()
        self.client.chat.assert_not_called()

    def test_demo_command_does_not_use_python_client(self):
        answer = handle_agent_command("демо: Проверить старую команду")

        self.assertIn("Агент: demo_agent", answer)
        self.assertIn("Статус: completed", answer)
        self.assertIn("Проверить старую команду", answer)
        self.client_factory.assert_not_called()
        self.client.chat.assert_not_called()

    def test_python_command_creates_default_client_when_needed(self):
        answer = handle_agent_command("python: Объясни словари.")

        self.client_factory.assert_called_once_with()
        self.client.chat.assert_called_once()
        self.assertIn("Объясни словари.", self.client.chat.call_args.args[0])
        self.assertIn("Агент: python_agent", answer)
        self.assertIn("Статус: completed", answer)

    def test_model_error_becomes_command_error_message(self):
        self.client.chat.side_effect = RuntimeError(
            "Тестовая ошибка модели."
        )

        answer = handle_agent_command(
            "python: Объясни генераторы.",
            python_client=self.client,
        )

        self.assertEqual(
            answer,
            "Ошибка выполнения: RuntimeError: Тестовая ошибка модели.",
        )
        self.client.chat.assert_called_once()
        self.client_factory.assert_not_called()

    def test_main_reuses_shared_adapter_and_saves_exchanges(self):
        app = importlib.import_module("main")
        session_id = "shared-router-test-session"
        conversation = [
            {"role": "system", "content": app.SYSTEM_PROMPT}
        ]
        prompts = [
            "демо: До Python.",
            "python: Объясни функции.",
            "демо: После Python.",
        ]
        python_answer = (
            "Агент: python_agent\n"
            "Статус: completed\n"
            "Результат: Тестовый ответ Python-агента"
        )
        output = io.StringIO()

        with ExitStack() as local:
            mocks = {}
            for name in (
                "init_db",
                "init_memory",
                "save_message",
                "load_messages",
                "list_sessions",
                "list_memories",
                "add_memory",
                "delete_memory",
                "choose_session",
                "ask_local_model",
            ):
                mocks[name] = local.enter_context(
                    patch.object(app, name, autospec=True)
                )

            mocks["choose_session"].return_value = (
                session_id,
                conversation,
            )
            mocks["list_memories"].return_value = []
            mocks["ask_local_model"].side_effect = AssertionError(
                "Команды агентов не должны попадать в обычный чат."
            )

            main_client_factory = local.enter_context(
                patch.object(
                    app,
                    "OllamaClient",
                    autospec=True,
                    return_value=self.client,
                )
            )
            adapter_factory = local.enter_context(
                patch.object(
                    app,
                    "create_router_adapter",
                    wraps=app.create_router_adapter,
                )
            )
            command_handler = local.enter_context(
                patch.object(
                    app,
                    "handle_agent_command",
                    wraps=app.handle_agent_command,
                )
            )

            local.enter_context(
                patch(
                    "builtins.input",
                    side_effect=[*prompts, "выход"],
                )
            )
            local.enter_context(redirect_stdout(output))

            app.main()

            mocks["init_db"].assert_called_once_with()
            mocks["init_memory"].assert_called_once_with()
            mocks["choose_session"].assert_called_once_with()
            mocks["ask_local_model"].assert_not_called()
            main_client_factory.assert_called_once_with(model=app.MODEL)
            adapter_factory.assert_called_once_with(self.client)

            self.assertEqual(command_handler.call_count, 3)
            shared_adapter = (
                command_handler.call_args_list[0].kwargs["router_adapter"]
            )
            self.assertEqual(
                command_handler.call_args_list,
                [
                    call(prompt, router_adapter=shared_adapter)
                    for prompt in prompts
                ],
            )

            self.assertEqual(len(conversation), 7)
            answers = [
                conversation[2]["content"],
                conversation[4]["content"],
                conversation[6]["content"],
            ]
            self.assertIn("Агент: demo_agent", answers[0])
            self.assertIn("Статус: completed", answers[0])
            self.assertIn("До Python.", answers[0])
            self.assertEqual(answers[1], python_answer)
            self.assertIn("Агент: demo_agent", answers[2])
            self.assertIn("Статус: completed", answers[2])
            self.assertIn("После Python.", answers[2])

            expected_messages = []
            expected_calls = []
            for prompt, answer in zip(prompts, answers):
                expected_messages.extend(
                    [
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": answer},
                    ]
                )
                expected_calls.extend(
                    [
                        call(session_id, "user", prompt),
                        call(session_id, "assistant", answer),
                    ]
                )
                self.assertIn(answer, output.getvalue())

            self.assertEqual(conversation[1:], expected_messages)
            self.assertEqual(
                mocks["save_message"].call_args_list,
                expected_calls,
            )

        self.client_factory.assert_not_called()
        self.client.chat.assert_called_once()
        self.assertIn(
            "Объясни функции.",
            self.client.chat.call_args.args[0],
        )


if __name__ == "__main__":
    unittest.main()
