"""Тесты Python-агента без реальной модели и рабочей базы данных."""

import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from router.executor import TaskExecutor
from router.python_agent import ChatClient, PythonAgentHandler
from router.registry import Agent
from router.task import Task, TaskStatus


class TestPythonAgent(unittest.TestCase):
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
        self.client.chat.return_value = "Тестовый ответ по Python"
        self.handler = PythonAgentHandler(self.client)
        self.executor = TaskExecutor()
        self.agent = Agent(
            agent_id="python_agent",
            name="Python Agent",
            role="Помощник по разработке на Python",
            capabilities=("python",),
        )

    def make_assigned_task(self, description):
        task = Task(
            description=description,
            required_capabilities=("python",),
        )
        task.assign(self.agent.agent_id)
        return task

    def test_creation_does_not_call_model(self):
        self.client.chat.assert_not_called()

    def test_handler_preserves_code_and_returns_client_answer(self):
        description = (
            "Объясни этот код:\n"
            "def greet(name):\n"
            "    return f'Привет, {name}!'\n"
            "\n"
            "print(greet('Анна'))"
        )
        task = self.make_assigned_task(description)
        expected_answer = (
            "Функция возвращает приветствие.\n\n"
            "```python\nprint(greet('Анна'))\n```"
        )
        self.client.chat.return_value = expected_answer

        answer = self.handler(task, self.agent)

        self.client.chat.assert_called_once()
        prompt = self.client.chat.call_args.args[0]
        self.assertIsInstance(prompt, str)
        self.assertIn(description, prompt)
        self.assertGreater(len(prompt), len(description))
        self.assertEqual(answer, expected_answer)

        # Статусом управляет исполнитель, а не обработчик.
        self.assertEqual(task.status, TaskStatus.ASSIGNED)
        self.assertIsNone(task.result)
        self.assertIsNone(task.error)

    def test_executor_completes_task_with_model_result(self):
        task = self.make_assigned_task("Объясни списки в Python.")

        def respond(prompt):
            self.assertEqual(task.status, TaskStatus.RUNNING)
            self.assertIn(task.description, prompt)
            return "Список хранит упорядоченную коллекцию элементов."

        self.client.chat.side_effect = respond

        returned_task = self.executor.execute(
            task, self.agent, self.handler
        )

        self.assertIs(returned_task, task)
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(
            task.result,
            "Список хранит упорядоченную коллекцию элементов.",
        )
        self.assertIsNone(task.error)
        self.assertEqual(task.assigned_agent_id, self.agent.agent_id)
        self.client.chat.assert_called_once()

    def test_model_error_becomes_failed_task(self):
        task = self.make_assigned_task("Объясни генераторы.")
        self.client.chat.side_effect = RuntimeError(
            "Тестовая ошибка подключения к модели."
        )

        returned_task = self.executor.execute(
            task, self.agent, self.handler
        )

        self.assertIs(returned_task, task)
        self.assertEqual(task.status, TaskStatus.FAILED)
        self.assertIsNone(task.result)
        self.assertEqual(
            task.error,
            "RuntimeError: Тестовая ошибка подключения к модели.",
        )
        self.client.chat.assert_called_once()

    def test_invalid_model_answers_become_failed_tasks(self):
        invalid_answers = ("", " \n\t ", None, 123, {"text": "ответ"})

        for invalid_answer in invalid_answers:
            with self.subTest(answer=invalid_answer):
                self.client.chat.reset_mock()
                self.client.chat.return_value = invalid_answer
                task = self.make_assigned_task("Объясни словари.")

                self.executor.execute(task, self.agent, self.handler)

                self.assertEqual(task.status, TaskStatus.FAILED)
                self.assertIsNone(task.result)
                self.assertIn(
                    "Агент должен вернуть непустой текстовый результат.",
                    task.error,
                )
                self.client.chat.assert_called_once()

    def test_reused_handler_keeps_tasks_independent(self):
        first = self.make_assigned_task(
            "Объясни функцию calculate_unique_alpha."
        )
        second = self.make_assigned_task(
            "Объясни функцию process_unique_beta."
        )
        self.client.chat.side_effect = [
            "Ответ только для первой задачи.",
            "Ответ только для второй задачи.",
        ]

        self.executor.execute(first, self.agent, self.handler)
        self.executor.execute(second, self.agent, self.handler)

        self.assertEqual(self.client.chat.call_count, 2)
        first_prompt = self.client.chat.call_args_list[0].args[0]
        second_prompt = self.client.chat.call_args_list[1].args[0]

        self.assertIn(first.description, first_prompt)
        self.assertNotIn(second.description, first_prompt)
        self.assertIn(second.description, second_prompt)
        self.assertNotIn(first.description, second_prompt)
        self.assertNotIn(first.result, second_prompt)

        self.assertEqual(first.status, TaskStatus.COMPLETED)
        self.assertEqual(second.status, TaskStatus.COMPLETED)
        self.assertEqual(first.result, "Ответ только для первой задачи.")
        self.assertEqual(second.result, "Ответ только для второй задачи.")


if __name__ == "__main__":
    unittest.main()