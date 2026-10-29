"""Интеграционные тесты Python-агента без Ollama и рабочей SQLite."""

import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from router.python_agent import ChatClient
from router.python_integration import (
    create_python_adapter,
    execute_python_task,
)
from router.task import TaskStatus


class TestPythonIntegration(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)

        for target in (
            "sqlite3.connect",
            "urllib.request.urlopen",
            "router.ollama_client.urlopen",
        ):
            self.stack.enter_context(
                patch(
                    target,
                    side_effect=AssertionError(
                        f"Внешнее обращение запрещено в тесте: {target}"
                    ),
                )
            )

        self.client = Mock(spec=ChatClient)
        self.client.chat.return_value = "Тестовый ответ Python-агента"

    def test_adapter_creation_does_not_call_model(self):
        create_python_adapter(self.client)

        self.client.chat.assert_not_called()

    def test_execute_python_task_returns_successful_agent_result(self):
        description = "Объясни разницу между списком и кортежем."
        expected = "Список изменяемый, а кортеж — неизменяемый."
        self.client.chat.return_value = expected

        result = execute_python_task(description, self.client)

        self.assertTrue(result.success)
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.agent_id, "python_agent")
        self.assertEqual(result.result, expected)
        self.assertIsInstance(result.task_id, str)
        self.assertTrue(result.task_id)
        self.assertTrue(result.message)

        self.client.chat.assert_called_once()
        prompt = self.client.chat.call_args.args[0]
        self.assertIn(description, prompt)

    def test_unsupported_capability_does_not_call_model(self):
        adapter = create_python_adapter(self.client)

        result = adapter.execute(
            description="Задача для другого специалиста.",
            required_capabilities=("devops",),
        )

        self.assertFalse(result.success)
        self.assertIsNone(result.agent_id)
        self.assertIsNone(result.result)
        self.assertTrue(result.message)
        self.client.chat.assert_not_called()

    def test_invalid_descriptions_are_rejected_before_model_call(self):
        for description in ("", " \n\t ", None, 123):
            with self.subTest(description=description):
                result = execute_python_task(description, self.client)

                self.assertFalse(result.success)
                self.assertIsNone(result.task_id)
                self.assertIsNone(result.status)
                self.assertIsNone(result.agent_id)
                self.assertIsNone(result.result)
                self.assertEqual(
                    result.message,
                    "Описание задачи не может быть пустым.",
                )
                self.client.chat.assert_not_called()

    def test_model_error_is_returned_as_failed_result(self):
        self.client.chat.side_effect = RuntimeError(
            "Тестовая ошибка модели."
        )

        result = execute_python_task(
            "Объясни обработку исключений.",
            self.client,
        )

        self.assertFalse(result.success)
        self.assertEqual(result.status, TaskStatus.FAILED)
        self.assertEqual(result.agent_id, "python_agent")
        self.assertTrue(result.task_id)
        self.assertIsNone(result.result)
        self.assertEqual(
            result.message,
            "RuntimeError: Тестовая ошибка модели.",
        )
        self.client.chat.assert_called_once()

    def test_invalid_model_answers_are_returned_as_failed_results(self):
        for answer in ("", " \n\t ", None, 123):
            with self.subTest(answer=answer):
                self.client.chat.reset_mock()
                self.client.chat.return_value = answer

                result = execute_python_task(
                    "Объясни функции.",
                    self.client,
                )

                self.assertFalse(result.success)
                self.assertEqual(result.status, TaskStatus.FAILED)
                self.assertEqual(result.agent_id, "python_agent")
                self.assertTrue(result.task_id)
                self.assertIsNone(result.result)
                self.assertIn(
                    "Агент должен вернуть непустой текстовый результат.",
                    result.message,
                )
                self.client.chat.assert_called_once()

    def test_same_adapter_handles_independent_tasks(self):
        adapter = create_python_adapter(self.client)
        self.client.chat.side_effect = [
            "Ответ о функции alpha_unique.",
            "Ответ о функции beta_unique.",
        ]

        first = adapter.execute(
            description="Объясни функцию alpha_unique.",
            required_capabilities=("python",),
        )
        second = adapter.execute(
            description="Объясни функцию beta_unique.",
            required_capabilities=("python",),
        )

        self.assertTrue(first.success)
        self.assertTrue(second.success)
        self.assertEqual(first.status, TaskStatus.COMPLETED)
        self.assertEqual(second.status, TaskStatus.COMPLETED)
        self.assertEqual(first.agent_id, "python_agent")
        self.assertEqual(second.agent_id, "python_agent")
        self.assertTrue(first.task_id)
        self.assertTrue(second.task_id)
        self.assertNotEqual(first.task_id, second.task_id)
        self.assertEqual(first.result, "Ответ о функции alpha_unique.")
        self.assertEqual(second.result, "Ответ о функции beta_unique.")

        self.assertEqual(self.client.chat.call_count, 2)
        first_prompt = self.client.chat.call_args_list[0].args[0]
        second_prompt = self.client.chat.call_args_list[1].args[0]
        self.assertIn("alpha_unique", first_prompt)
        self.assertNotIn("beta_unique", first_prompt)
        self.assertIn("beta_unique", second_prompt)
        self.assertNotIn("alpha_unique", second_prompt)


if __name__ == "__main__":
    unittest.main()