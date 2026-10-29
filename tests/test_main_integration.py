"""Проверки main.py без рабочей SQLite и реального обращения к Ollama."""

import copy
import importlib
import io
import unittest
from contextlib import ExitStack, redirect_stdout
from unittest.mock import call, patch


class TestMainIntegration(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)

        self.sqlite_connect = self.stack.enter_context(
            patch(
                "sqlite3.connect",
                side_effect=AssertionError(
                    "Реальное подключение SQLite запрещено в этом тесте."
                ),
            )
        )
        self.urlopen = self.stack.enter_context(
            patch(
                "urllib.request.urlopen",
                side_effect=AssertionError(
                    "Реальный HTTP-запрос запрещён в этом тесте."
                ),
            )
        )

        self.app = importlib.import_module("main")
        self.session_id = "integration-test-session"
        self.conversation = [
            {"role": "system", "content": self.app.SYSTEM_PROMPT}
        ]

        self.mocks = {}
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
            self.mocks[name] = self.stack.enter_context(
                patch.object(self.app, name, autospec=True)
            )

        self.mocks["choose_session"].return_value = (
            self.session_id,
            self.conversation,
        )
        self.mocks["list_memories"].return_value = []
        self.mocks["load_messages"].return_value = []
        self.mocks["list_sessions"].return_value = []
        self.mocks["add_memory"].return_value = 7
        self.mocks["delete_memory"].return_value = True
        self.mocks["ask_local_model"].side_effect = AssertionError(
            "Для этой команды модель вызываться не должна."
        )

    def run_dialog(self, *prompts):
        output = io.StringIO()
        with (
            patch("builtins.input", side_effect=[*prompts, "выход"]),
            redirect_stdout(output),
        ):
            self.app.main()

        self.mocks["init_db"].assert_called_once_with()
        self.mocks["init_memory"].assert_called_once_with()
        self.sqlite_connect.assert_not_called()
        self.urlopen.assert_not_called()
        return output.getvalue()

    def assert_exchange_saved(self, prompt, answer):
        self.assertEqual(
            self.mocks["save_message"].call_args_list,
            [
                call(self.session_id, "user", prompt),
                call(self.session_id, "assistant", answer),
            ],
        )
        self.assertEqual(
            self.conversation[1:],
            [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": answer},
            ],
        )

    def test_demo_command_runs_agent_without_model(self):
        prompt = "демо: Проверить маршрутизацию"
        output = self.run_dialog(prompt)

        answer = self.conversation[-1]["content"]
        self.assertIn("Агент: demo_agent", answer)
        self.assertIn("Статус: completed", answer)
        self.assertIn("Описание: Проверить маршрутизацию", answer)
        self.assertIn(answer, output)
        self.mocks["ask_local_model"].assert_not_called()
        self.assert_exchange_saved(prompt, answer)

    def test_demo_command_accepts_uppercase_and_spaces(self):
        self.run_dialog("  ДЕМО:   Проверить регистр  ")

        answer = self.conversation[-1]["content"]
        self.assertIn("Агент: demo_agent", answer)
        self.assertIn("Описание: Проверить регистр", answer)
        self.mocks["ask_local_model"].assert_not_called()
        self.assert_exchange_saved(
            "ДЕМО:   Проверить регистр",
            answer,
        )

    def test_empty_demo_command_does_not_run_agent_or_model(self):
        with patch(
            "router.commands.execute_demo_task",
            side_effect=AssertionError(
                "Пустая команда не должна запускать агента."
            ),
        ) as execute:
            output = self.run_dialog("демо:")
            execute.assert_not_called()

        answer = (
            "Ошибка: после команды 'демо:' "
            "необходимо указать описание задачи."
        )
        self.assertIn(answer, output)
        self.mocks["ask_local_model"].assert_not_called()
        self.assert_exchange_saved("демо:", answer)

    def test_regular_message_uses_model_and_saves_answer(self):
        received = []

        def fake_model(messages):
            received.append(copy.deepcopy(messages))
            return "Тестовый ответ модели"

        self.mocks["ask_local_model"].side_effect = fake_model
        output = self.run_dialog("Привет")

        self.mocks["ask_local_model"].assert_called_once()
        self.assertEqual(
            received,
            [[
                {"role": "system", "content": self.app.SYSTEM_PROMPT},
                {"role": "user", "content": "Привет"},
            ]],
        )
        self.assertIn("Тестовый ответ модели", output)
        self.assert_exchange_saved("Привет", "Тестовый ответ модели")

    def test_dialog_continues_after_agent_and_preserves_history(self):
        received = []

        def fake_model(messages):
            received.append(copy.deepcopy(messages))
            return "Продолжаем диалог"

        self.mocks["ask_local_model"].side_effect = fake_model
        self.run_dialog("демо: Проверить историю", "Что дальше?")

        self.mocks["ask_local_model"].assert_called_once()
        agent_answer = self.conversation[2]["content"]
        self.assertIn("Агент: demo_agent", agent_answer)
        self.assertEqual(received, [self.conversation[:-1]])
        self.assertEqual(
            self.mocks["save_message"].call_args_list,
            [
                call(
                    self.session_id,
                    "user",
                    "демо: Проверить историю",
                ),
                call(self.session_id, "assistant", agent_answer),
                call(self.session_id, "user", "Что дальше?"),
                call(
                    self.session_id,
                    "assistant",
                    "Продолжаем диалог",
                ),
            ],
        )

    def test_show_memory_bypasses_agent_model_and_message_storage(self):
        self.mocks["list_memories"].return_value = [
            {"id": 7, "content": "Тестовый факт"}
        ]

        with patch.object(
            self.app,
            "handle_agent_command",
            side_effect=AssertionError(
                "Команда памяти не должна передаваться агенту."
            ),
        ) as agent_command:
            output = self.run_dialog("память")
            agent_command.assert_not_called()

        self.assertIn("7. Тестовый факт", output)
        self.mocks["ask_local_model"].assert_not_called()
        self.mocks["save_message"].assert_not_called()
        self.assertEqual(len(self.conversation), 1)

    def test_remember_refreshes_context_without_real_database(self):
        self.mocks["list_memories"].return_value = [
            {"id": 7, "content": "Я изучаю Python"}
        ]

        with patch.object(self.app, "handle_agent_command") as agent_command:
            output = self.run_dialog("запомни: Я изучаю Python")
            agent_command.assert_not_called()

        self.mocks["add_memory"].assert_called_once_with(
            "Я изучаю Python"
        )
        self.assertIn("Факт сохранён. Номер: 7", output)
        self.assertIn(
            "- [7] Я изучаю Python",
            self.conversation[0]["content"],
        )
        self.mocks["ask_local_model"].assert_not_called()
        self.mocks["save_message"].assert_not_called()
        self.assertEqual(len(self.conversation), 1)

    def test_forget_refreshes_context_without_real_database(self):
        self.conversation[0]["content"] = (
            self.app.SYSTEM_PROMPT + "\n- [7] Тестовый факт"
        )

        with patch.object(self.app, "handle_agent_command") as agent_command:
            output = self.run_dialog("забудь: 7")
            agent_command.assert_not_called()

        self.mocks["delete_memory"].assert_called_once_with(7)
        self.assertIn("Факт № 7 удалён.", output)
        self.assertEqual(
            self.conversation,
            [{"role": "system", "content": self.app.SYSTEM_PROMPT}],
        )
        self.mocks["ask_local_model"].assert_not_called()
        self.mocks["save_message"].assert_not_called()


if __name__ == "__main__":
    unittest.main()