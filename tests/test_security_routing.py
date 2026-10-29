
"""Интеграционные тесты маршрутизации агента безопасности."""

import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from router.bootstrap import create_router_adapter
from router.python_agent import ChatClient
from router.security_agent import SECURITY_AGENT_INSTRUCTIONS
from router.task import TaskStatus


class TestSecurityRouting(unittest.TestCase):
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
        self.client.chat.return_value = "Отчёт проверки безопасности."
        self.adapter = create_router_adapter(self.client)

    def execute_security(self, description):
        return self.adapter.execute(
            description=description,
            required_capabilities=("security",),
        )

    def test_security_capability_selects_security_agent(self):
        result = self.execute_security(
            "Проверь безопасность функции read_file."
        )

        self.assertTrue(result.success)
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.agent_id, "security_agent")
        self.assertEqual(result.result, "Отчёт проверки безопасности.")
        self.assertTrue(result.task_id)
        self.client.chat.assert_called_once()

    def test_requirements_and_code_reach_security_handler(self):
        description = (
            "ТРЕБОВАНИЯ:\n"
            "Получать пользователя по имени без SQL-инъекций.\n\n"
            "КОД:\n"
            "def find_user(cursor, name):\n"
            '    query = f"SELECT * FROM users WHERE name = \'{name}\'"\n'
            "    return cursor.execute(query).fetchone()"
        )

        result = self.execute_security(description)

        self.assertTrue(result.success)

        expected_prompt = (
            SECURITY_AGENT_INSTRUCTIONS
            + "\n\nМАТЕРИАЛЫ ДЛЯ ПРОВЕРКИ:\n"
            + description
        )
        self.client.chat.assert_called_once_with(expected_prompt)

    def test_security_report_is_preserved(self):
        report = (
            "Область проверки: SQL-запрос.\n"
            "Замечания: возможна SQL-инъекция.\n"
            "Исправление: параметризованный запрос.\n"
            "Проверка: тест с недоверенным именем.\n"
            "Ограничения: код не запускался."
        )
        self.client.chat.return_value = report

        result = self.execute_security("Проверь SQL-запрос.")

        self.assertTrue(result.success)
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.result, report)

    def test_model_error_becomes_failed_task(self):
        self.client.chat.side_effect = RuntimeError(
            "Тестовая ошибка Security Agent."
        )

        result = self.execute_security(
            "Проверь использование subprocess."
        )

        self.assertFalse(result.success)
        self.assertEqual(result.status, TaskStatus.FAILED)
        self.assertEqual(result.agent_id, "security_agent")
        self.assertIsNone(result.result)
        self.assertIn(
            "Тестовая ошибка Security Agent.",
            result.message,
        )
        self.client.chat.assert_called_once()

    def test_invalid_security_answers_are_rejected(self):
        for answer in ("", " \n\t ", None, 123, {"report": "text"}):
            with self.subTest(answer=answer):
                self.client.chat.reset_mock()
                self.client.chat.side_effect = None
                self.client.chat.return_value = answer

                result = self.execute_security(
                    "Проверь обработку пользовательского ввода."
                )

                self.assertFalse(result.success)
                self.assertEqual(result.status, TaskStatus.FAILED)
                self.assertEqual(result.agent_id, "security_agent")
                self.assertIsNone(result.result)
                self.assertIn(
                    "Агент должен вернуть непустой текстовый результат.",
                    result.message,
                )
                self.client.chat.assert_called_once()

    def test_python_and_security_tasks_are_independent(self):
        self.client.chat.side_effect = [
            "Код первой версии Python.",
            "Отчёт Security Agent.",
            "Код второй версии Python.",
        ]

        first = self.adapter.execute(
            description="Напиши функцию alpha_unique.",
            required_capabilities=("python",),
        )

        second = self.execute_security(
            "Проверь код функции beta_unique."
        )

        third = self.adapter.execute(
            description="Исправь функцию gamma_unique.",
            required_capabilities=("python",),
        )

        results = (first, second, third)

        self.assertTrue(all(result.success for result in results))
        self.assertTrue(
            all(
                result.status == TaskStatus.COMPLETED
                for result in results
            )
        )

        self.assertEqual(
            [result.agent_id for result in results],
            ["python_agent", "security_agent", "python_agent"],
        )
        self.assertEqual(
            len({result.task_id for result in results}),
            3,
        )
        self.assertEqual(
            [result.result for result in results],
            [
                "Код первой версии Python.",
                "Отчёт Security Agent.",
                "Код второй версии Python.",
            ],
        )

        prompts = [
            entry.args[0]
            for entry in self.client.chat.call_args_list
        ]

        self.assertEqual(len(prompts), 3)
        self.assertIn("alpha_unique", prompts[0])
        self.assertNotIn("beta_unique", prompts[0])
        self.assertIn("beta_unique", prompts[1])
        self.assertNotIn("alpha_unique", prompts[1])
        self.assertNotIn("Код первой версии Python.", prompts[1])
        self.assertIn("gamma_unique", prompts[2])
        self.assertNotIn("beta_unique", prompts[2])

    def test_error_does_not_break_later_security_task(self):
        self.client.chat.side_effect = [
            RuntimeError("Первая проверка недоступна."),
            "Проверка восстановлена.",
        ]

        failed = self.execute_security(
            "Первая проверка безопасности."
        )

        demo = self.adapter.execute(
            description="Демонстрационная задача после ошибки.",
            required_capabilities=("demo",),
        )

        recovered = self.execute_security(
            "Повторная проверка безопасности."
        )

        self.assertFalse(failed.success)
        self.assertEqual(failed.status, TaskStatus.FAILED)
        self.assertEqual(failed.agent_id, "security_agent")

        self.assertTrue(demo.success)
        self.assertEqual(demo.status, TaskStatus.COMPLETED)
        self.assertEqual(demo.agent_id, "demo_agent")

        self.assertTrue(recovered.success)
        self.assertEqual(recovered.status, TaskStatus.COMPLETED)
        self.assertEqual(recovered.agent_id, "security_agent")
        self.assertEqual(
            recovered.result,
            "Проверка восстановлена.",
        )

        self.assertEqual(self.client.chat.call_count, 2)
        self.assertEqual(
            len({failed.task_id, demo.task_id, recovered.task_id}),
            3,
        )

        # Новая задача не меняет ранее зафиксированную ошибку.
        self.assertEqual(failed.status, TaskStatus.FAILED)
        self.assertIsNone(failed.result)


if __name__ == "__main__":
    unittest.main()
