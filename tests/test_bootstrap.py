"""Проверки общего маршрутизатора без реальной модели и SQLite."""

import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from router.bootstrap import create_router_adapter
from router.python_agent import ChatClient
from router.task import TaskStatus


class TestBootstrap(unittest.TestCase):
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
        self.client.chat.return_value = "Ответ Python-агента"
        self.adapter = create_router_adapter(self.client)

    def test_creation_does_not_call_model(self):
        self.client.chat.assert_not_called()

    def test_demo_capability_selects_demo_without_model_call(self):
        result = self.adapter.execute(
            description="Проверить демонстрационный маршрут.",
            required_capabilities=("demo",),
        )

        self.assertTrue(result.success)
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.agent_id, "demo_agent")
        self.assertIn(
            "Проверить демонстрационный маршрут.",
            result.result,
        )
        self.assertTrue(result.task_id)
        self.client.chat.assert_not_called()

    def test_python_capability_selects_python_agent(self):
        description = "Объясни функцию enumerate."

        result = self.adapter.execute(
            description=description,
            required_capabilities=("python",),
        )

        self.assertTrue(result.success)
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.agent_id, "python_agent")
        self.assertEqual(result.result, "Ответ Python-агента")
        self.assertTrue(result.task_id)
        self.client.chat.assert_called_once()
        self.assertIn(description, self.client.chat.call_args.args[0])

    def test_same_adapter_routes_alternating_tasks_independently(self):
        first = self.adapter.execute(
            description="Демо-задача alpha_unique.",
            required_capabilities=("demo",),
        )
        second = self.adapter.execute(
            description="Python-задача beta_unique.",
            required_capabilities=("python",),
        )
        third = self.adapter.execute(
            description="Демо-задача gamma_unique.",
            required_capabilities=("demo",),
        )

        for result in (first, second, third):
            self.assertTrue(result.success)
            self.assertEqual(result.status, TaskStatus.COMPLETED)
            self.assertTrue(result.task_id)

        self.assertEqual(
            [first.agent_id, second.agent_id, third.agent_id],
            ["demo_agent", "python_agent", "demo_agent"],
        )
        self.assertEqual(
            len({first.task_id, second.task_id, third.task_id}),
            3,
        )
        self.assertIn("alpha_unique", first.result)
        self.assertEqual(second.result, "Ответ Python-агента")
        self.assertIn("gamma_unique", third.result)
        self.assertNotIn("alpha_unique", third.result)

        self.client.chat.assert_called_once()
        model_prompt = self.client.chat.call_args.args[0]
        self.assertIn("beta_unique", model_prompt)
        self.assertNotIn("alpha_unique", model_prompt)
        self.assertNotIn("gamma_unique", model_prompt)

    def test_unavailable_capabilities_do_not_call_model(self):
        for capabilities in (
            ("devops",),
            ("demo", "python"),
        ):
            with self.subTest(capabilities=capabilities):
                result = self.adapter.execute(
                    description="Задача без подходящего исполнителя.",
                    required_capabilities=capabilities,
                )

                self.assertFalse(result.success)
                self.assertIsNone(result.agent_id)
                self.assertIsNone(result.result)
                self.assertTrue(result.message)

        self.client.chat.assert_not_called()

    def test_invalid_description_does_not_create_task_or_call_model(self):
        for description in ("", " \n\t ", None, 123):
            with self.subTest(description=description):
                result = self.adapter.execute(
                    description=description,
                    required_capabilities=("python",),
                )

                self.assertFalse(result.success)
                self.assertIsNone(result.task_id)
                self.assertIsNone(result.status)
                self.assertIsNone(result.agent_id)
                self.assertIsNone(result.result)

        self.client.chat.assert_not_called()

    def test_model_failure_does_not_break_later_tasks(self):
        self.client.chat.side_effect = [
            RuntimeError("Тестовая ошибка модели."),
            "Ответ после восстановления.",
        ]

        failed = self.adapter.execute(
            description="Первая Python-задача.",
            required_capabilities=("python",),
        )

        self.assertFalse(failed.success)
        self.assertEqual(failed.status, TaskStatus.FAILED)
        self.assertEqual(failed.agent_id, "python_agent")
        self.assertIsNone(failed.result)
        self.assertIn("Тестовая ошибка модели.", failed.message)

        demo = self.adapter.execute(
            description="Демо после ошибки.",
            required_capabilities=("demo",),
        )

        self.assertTrue(demo.success)
        self.assertEqual(demo.status, TaskStatus.COMPLETED)
        self.assertEqual(demo.agent_id, "demo_agent")
        self.assertEqual(self.client.chat.call_count, 1)

        recovered = self.adapter.execute(
            description="Вторая Python-задача.",
            required_capabilities=("python",),
        )

        self.assertTrue(recovered.success)
        self.assertEqual(recovered.status, TaskStatus.COMPLETED)
        self.assertEqual(recovered.agent_id, "python_agent")
        self.assertEqual(recovered.result, "Ответ после восстановления.")
        self.assertEqual(self.client.chat.call_count, 2)

        # Новые задачи не изменили результат ранее завершённой задачи.
        self.assertEqual(failed.status, TaskStatus.FAILED)
        self.assertIsNone(failed.result)
        self.assertEqual(
            len({failed.task_id, demo.task_id, recovered.task_id}),
            3,
        )


if __name__ == "__main__":
    unittest.main()