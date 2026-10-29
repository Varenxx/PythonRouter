"""Проверки python-check: без реальной Ollama и рабочей SQLite."""

import importlib
import io
import unittest
from contextlib import ExitStack, redirect_stdout
from unittest.mock import Mock, call, patch

from router.bootstrap import create_router_adapter
from router.commands import handle_agent_command
from router.python_agent import ChatClient


class TestWorkflowCommands(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)

        for target in (
            "sqlite3.connect",
            "urllib.request.urlopen",
            "router.ollama_client.urlopen",
            "router.commands.OllamaClient",
            "router.commands.execute_python_task",
            "router.commands.execute_demo_task",
        ):
            blocker = self.stack.enter_context(
                patch(
                    target,
                    side_effect=AssertionError(
                        f"Запрещённый вызов в тесте workflow: {target}"
                    ),
                )
            )
            self.addCleanup(blocker.assert_not_called)

        self.code = "```python\ndef add(a, b):\n    return a + b\n```"
        self.report = "Проверен предоставленный код. Нужны тесты."
        self.client = Mock(spec=ChatClient)
        self.client.chat.side_effect = [self.code, self.report]
        self.adapter = create_router_adapter(self.client)
        self.execute = self.stack.enter_context(
            patch.object(
                self.adapter,
                "execute",
                wraps=self.adapter.execute,
            )
        )

    def run_command(self, prompt):
        return handle_agent_command(prompt, router_adapter=self.adapter)

    def test_success_routes_exact_materials_and_shows_both_results(self):
        requirements = "Напиши функцию add(a, b)."

        answer = self.run_command("python-check: " + requirements)

        security_description = (
            "ИСХОДНЫЕ ТРЕБОВАНИЯ:\n"
            + requirements
            + "\n\nКОД И ОТВЕТ PYTHON AGENT ДЛЯ ПРОВЕРКИ:\n"
            + self.code
        )
        self.assertEqual(
            self.execute.call_args_list,
            [
                call(
                    description=requirements,
                    required_capabilities=("python",),
                ),
                call(
                    description=security_description,
                    required_capabilities=("security",),
                ),
            ],
        )
        self.assertEqual(self.client.chat.call_count, 2)
        self.assertIn(requirements, self.client.chat.call_args_list[0].args[0])
        self.assertIn(
            security_description,
            self.client.chat.call_args_list[1].args[0],
        )
        self.assertIn("Технический результат: завершено", answer)
        self.assertIn("Агент: python_agent\nСтатус: completed", answer)
        self.assertIn("Агент: security_agent\nСтатус: completed", answer)
        self.assertIn("Ответ Python Agent:\n" + self.code, answer)
        self.assertIn("Отчёт Security Agent:\n" + self.report, answer)
        self.assertIn("не доказывает безопасность кода", answer)
        self.assertIn("Сгенерированный код не выполнялся", answer)

    def test_uppercase_spaces_and_colons_preserve_requirements(self):
        requirements = (
            "Объясни код:\n"
            "def greet(name):\n"
            "    return f'Привет: {name}'"
        )

        answer = self.run_command("  PYTHON-CHECK:   " + requirements + "  ")

        self.assertIn("Технический результат: завершено", answer)
        self.assertEqual(self.execute.call_count, 2)
        self.assertEqual(
            self.execute.call_args_list[0],
            call(description=requirements, required_capabilities=("python",)),
        )
        self.assertIn(requirements, self.client.chat.call_args_list[1].args[0])

    def test_empty_command_does_not_start_agents(self):
        for prompt in ("python-check:", " PYTHON-CHECK: \n\t "):
            with self.subTest(prompt=prompt):
                self.assertEqual(
                    self.run_command(prompt),
                    "Ошибка: после команды 'python-check:' "
                    "необходимо указать описание задачи.",
                )

        self.execute.assert_not_called()
        self.client.chat.assert_not_called()

    def test_command_requires_shared_adapter(self):
        for dependencies in ({}, {"python_client": self.client}):
            with self.subTest(dependencies=tuple(dependencies)):
                answer = handle_agent_command(
                    "python-check: Напиши функцию.",
                    **dependencies,
                )
                self.assertEqual(
                    answer,
                    "Ошибка: для команды 'python-check:' "
                    "необходим общий маршрутизатор.",
                )

        self.execute.assert_not_called()
        self.client.chat.assert_not_called()

    def test_other_input_does_not_start_workflow(self):
        for prompt in (
            "python-check",
            "python-checker: пример",
            "Объясни python-check: команда",
            "",
            None,
            123,
        ):
            with self.subTest(prompt=prompt):
                self.assertIsNone(self.run_command(prompt))

        self.execute.assert_not_called()
        self.client.chat.assert_not_called()

    def test_python_failure_does_not_start_security(self):
        self.client.chat.side_effect = RuntimeError("Сбой Python.")

        answer = self.run_command("python-check: Напиши функцию.")

        self.client.chat.assert_called_once()
        self.execute.assert_called_once_with(
            description="Напиши функцию.",
            required_capabilities=("python",),
        )
        self.assertIn("Технический результат: ошибка", answer)
        self.assertIn("Агент: python_agent\nСтатус: failed", answer)
        self.assertIn("Сбой Python.", answer)
        self.assertIn("Security Agent: этап не запускался.", answer)
        self.assertIn("Ответ Python Agent не получен.", answer)
        self.assertIn("Отчёт Security Agent не получен.", answer)

    def test_security_failure_keeps_python_response(self):
        self.client.chat.side_effect = [
            self.code,
            RuntimeError("Сбой Security."),
        ]

        answer = self.run_command("python-check: Напиши функцию.")

        self.assertEqual(self.client.chat.call_count, 2)
        self.assertEqual(self.execute.call_count, 2)
        self.assertIn("Технический результат: ошибка", answer)
        self.assertIn("Агент: python_agent\nСтатус: completed", answer)
        self.assertIn("Агент: security_agent\nСтатус: failed", answer)
        self.assertIn("Ответ Python Agent:\n" + self.code, answer)
        self.assertIn("Сбой Security.", answer)
        self.assertIn("Отчёт Security Agent не получен.", answer)

    def test_new_command_works_after_security_failure(self):
        second_code = "```python\ndef square(x):\n    return x * x\n```"
        self.client.chat.side_effect = [
            self.code,
            RuntimeError("Первая проверка не удалась."),
            second_code,
            "Второй отчёт.",
        ]

        failed = self.run_command("python-check: Первая задача.")
        recovered = self.run_command("python-check: Вторая задача.")

        self.assertIn("Технический результат: ошибка", failed)
        self.assertIn(self.code, failed)
        self.assertIn("Технический результат: завершено", recovered)
        self.assertIn(second_code, recovered)
        self.assertIn("Второй отчёт.", recovered)
        self.assertNotIn(self.code, recovered)
        self.assertEqual(self.client.chat.call_count, 4)
        self.assertEqual(self.execute.call_count, 4)

    def test_report_with_findings_is_not_treated_as_execution_failure(self):
        report = "Найдена серьёзная проблема. Код требует исправления."
        self.client.chat.side_effect = [self.code, report]

        answer = self.run_command("python-check: Напиши функцию.")

        self.assertIn("Технический результат: завершено", answer)
        self.assertIn("Отчёт Security Agent:\n" + report, answer)
        self.assertIn("не доказывает безопасность кода", answer)
        self.assertEqual(self.client.chat.call_count, 2)

    def test_main_saves_workflow_response_and_continues_after_security_error(self):
        app = importlib.import_module("main")
        session_id = "workflow-command-test-session"
        conversation = [{"role": "system", "content": app.SYSTEM_PROMPT}]
        prompts = [
            "python-check: Напиши функцию.",
            "демо: Продолжить после ошибки проверки.",
        ]
        self.client.chat.side_effect = [
            self.code,
            RuntimeError("Проверка временно недоступна."),
        ]
        output = io.StringIO()

        with ExitStack() as local:
            mocks = {}
            for name in (
                "init_db", "init_memory", "save_message", "load_messages",
                "list_sessions", "list_memories", "add_memory", "delete_memory",
                "choose_session", "ask_local_model",
            ):
                mocks[name] = local.enter_context(
                    patch.object(app, name, autospec=True)
                )

            mocks["choose_session"].return_value = (session_id, conversation)
            mocks["list_memories"].return_value = []
            mocks["ask_local_model"].side_effect = AssertionError(
                "Команда workflow не должна попадать в обычный чат."
            )
            client_factory = local.enter_context(
                patch.object(app, "OllamaClient", return_value=self.client)
            )
            adapter_factory = local.enter_context(
                patch.object(app, "create_router_adapter", return_value=self.adapter)
            )
            handler = local.enter_context(
                patch.object(app, "handle_agent_command", wraps=app.handle_agent_command)
            )
            local.enter_context(patch("builtins.input", side_effect=[*prompts, "выход"]))
            local.enter_context(redirect_stdout(output))

            app.main()

            client_factory.assert_called_once_with(model=app.MODEL)
            adapter_factory.assert_called_once_with(self.client)
            mocks["ask_local_model"].assert_not_called()
            self.assertEqual(
                handler.call_args_list,
                [call(prompt, router_adapter=self.adapter) for prompt in prompts],
            )
            self.assertEqual(len(conversation), 5)
            workflow_answer = conversation[2]["content"]
            demo_answer = conversation[4]["content"]
            self.assertIn("Технический результат: ошибка", workflow_answer)
            self.assertIn(self.code, workflow_answer)
            self.assertIn("Проверка временно недоступна.", workflow_answer)
            self.assertIn("Агент: demo_agent", demo_answer)
            self.assertIn("Статус: completed", demo_answer)
            self.assertIn(workflow_answer, output.getvalue())
            self.assertIn(demo_answer, output.getvalue())
            self.assertEqual(
                mocks["save_message"].call_args_list,
                [
                    call(session_id, "user", prompts[0]),
                    call(session_id, "assistant", workflow_answer),
                    call(session_id, "user", prompts[1]),
                    call(session_id, "assistant", demo_answer),
                ],
            )
            self.assertEqual(
                conversation[1:],
                [
                    {"role": "user", "content": prompts[0]},
                    {"role": "assistant", "content": workflow_answer},
                    {"role": "user", "content": prompts[1]},
                    {"role": "assistant", "content": demo_answer},
                ],
            )

        self.assertEqual(self.client.chat.call_count, 2)
        self.assertEqual(self.execute.call_count, 3)


if __name__ == "__main__":
    unittest.main()