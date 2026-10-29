
"""Тесты последовательной работы Python Agent и Security Agent."""

import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from router.bootstrap import create_router_adapter
from router.python_agent import ChatClient
from router.task import TaskStatus
from router.workflow import PythonSecurityWorkflow


class TestPythonSecurityWorkflow(unittest.TestCase):
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
        self.adapter = create_router_adapter(self.client)
        self.workflow = PythonSecurityWorkflow(self.adapter)

    def test_creation_does_not_call_model(self):
        self.client.chat.assert_not_called()

    def test_successful_workflow_runs_python_then_security(self):
        requirements = "Напиши функцию безопасного чтения CSV."
        code = "def read_csv(path):\n    return []"
        report = "Отчёт: необходимо проверить обработку ошибок."

        self.client.chat.side_effect = [code, report]

        result = self.workflow.run(requirements)

        self.assertTrue(result.success)
        self.assertEqual(result.requirements, requirements)
        self.assertEqual(result.code, code)
        self.assertEqual(result.security_report, report)

        self.assertEqual(result.python_step.agent_id, "python_agent")
        self.assertEqual(result.security_step.agent_id, "security_agent")

        self.assertEqual(
            result.python_step.status,
            TaskStatus.COMPLETED,
        )
        self.assertEqual(
            result.security_step.status,
            TaskStatus.COMPLETED,
        )
        self.assertEqual(self.client.chat.call_count, 2)

        first_prompt = self.client.chat.call_args_list[0].args[0]
        second_prompt = self.client.chat.call_args_list[1].args[0]

        self.assertIn(requirements, first_prompt)
        self.assertIn(requirements, second_prompt)
        self.assertIn(code, second_prompt)
        self.assertNotIn(report, first_prompt)

    def test_security_receives_exact_requirements_and_code(self):
        requirements = (
            "ТРЕБОВАНИЯ:\n"
            "Обработать пользовательское имя.\n"
            "Не выполнять SQL через конкатенацию строк."
        )
        code = (
            "```python\n"
            "def find_user(cursor, name):\n"
            '    return cursor.execute("SELECT * FROM users WHERE name = ?", '
            "(name,)).fetchone()\n"
            "```"
        )

        self.client.chat.side_effect = [code, "Замечаний не обнаружено."]

        result = self.workflow.run(requirements)

        self.assertTrue(result.success)

        security_prompt = self.client.chat.call_args_list[1].args[0]

        expected_materials = (
            "ИСХОДНЫЕ ТРЕБОВАНИЯ:\n"
            + requirements
            + "\n\n"
            + "КОД И ОТВЕТ PYTHON AGENT ДЛЯ ПРОВЕРКИ:\n"
            + code
        )

        self.assertIn(expected_materials, security_prompt)
        self.assertEqual(result.code, code)
        self.assertEqual(result.requirements, requirements)

    def test_python_failure_stops_before_security(self):
        self.client.chat.side_effect = RuntimeError(
            "Тестовая ошибка Python Agent."
        )

        result = self.workflow.run("Напиши функцию calculate.")

        self.assertFalse(result.success)
        self.assertIsNone(result.code)
        self.assertIsNone(result.security_report)
        self.assertIsNotNone(result.python_step)
        self.assertIsNone(result.security_step)

        self.assertEqual(
            result.python_step.status,
            TaskStatus.FAILED,
        )
        self.assertIn(
            "Тестовая ошибка Python Agent.",
            result.message,
        )
        self.client.chat.assert_called_once()

    def test_security_failure_preserves_python_code(self):
        code = "def calculate(a, b):\n    return a + b"

        self.client.chat.side_effect = [
            code,
            RuntimeError("Тестовая ошибка Security Agent."),
        ]

        result = self.workflow.run("Напиши функцию calculate.")

        self.assertFalse(result.success)
        self.assertEqual(result.code, code)
        self.assertIsNone(result.security_report)

        self.assertEqual(
            result.python_step.status,
            TaskStatus.COMPLETED,
        )
        self.assertEqual(
            result.security_step.status,
            TaskStatus.FAILED,
        )
        self.assertIn(
            "Тестовая ошибка Security Agent.",
            result.message,
        )
        self.assertEqual(self.client.chat.call_count, 2)

    def test_invalid_requirements_do_not_call_model(self):
        for requirements in ("", " \n\t ", None, 123):
            with self.subTest(requirements=requirements):
                result = self.workflow.run(requirements)

                self.assertFalse(result.success)
                self.assertIsNone(result.code)
                self.assertIsNone(result.security_report)
                self.assertIsNone(result.python_step)
                self.assertIsNone(result.security_step)
                self.assertIn(
                    "Требования не могут быть пустыми.",
                    result.message,
                )

        self.client.chat.assert_not_called()

    def test_invalid_python_answer_prevents_security(self):
        for answer in ("", " \n\t ", None, 123):
            with self.subTest(answer=answer):
                self.client.chat.reset_mock()
                self.client.chat.side_effect = None
                self.client.chat.return_value = answer

                result = self.workflow.run(
                    "Напиши функцию обработки данных."
                )

                self.assertFalse(result.success)
                self.assertIsNone(result.code)
                self.assertIsNone(result.security_step)
                self.assertEqual(
                    result.python_step.status,
                    TaskStatus.FAILED,
                )
                self.client.chat.assert_called_once()

    def test_sequential_runs_keep_results_independent(self):
        self.client.chat.side_effect = [
            "Код alpha_unique.",
            "Отчёт alpha_security.",
            "Код beta_unique.",
            "Отчёт beta_security.",
        ]

        first = self.workflow.run("Требования alpha_unique.")
        second = self.workflow.run("Требования beta_unique.")

        self.assertTrue(first.success)
        self.assertTrue(second.success)

        self.assertEqual(first.code, "Код alpha_unique.")
        self.assertEqual(second.code, "Код beta_unique.")

        self.assertEqual(
            first.security_report,
            "Отчёт alpha_security.",
        )
        self.assertEqual(
            second.security_report,
            "Отчёт beta_security.",
        )

        self.assertEqual(self.client.chat.call_count, 4)

        prompts = [
            item.args[0]
            for item in self.client.chat.call_args_list
        ]

        self.assertIn("alpha_unique", prompts[0])
        self.assertIn("Код alpha_unique.", prompts[1])
        self.assertNotIn("beta_unique", prompts[1])

        self.assertIn("beta_unique", prompts[2])
        self.assertNotIn("alpha_unique", prompts[2])
        self.assertIn("Код beta_unique.", prompts[3])
        self.assertNotIn("Код alpha_unique.", prompts[3])

        task_ids = {
            first.python_step.task_id,
            first.security_step.task_id,
            second.python_step.task_id,
            second.security_step.task_id,
        }
        self.assertEqual(len(task_ids), 4)


if __name__ == "__main__":
    unittest.main()
