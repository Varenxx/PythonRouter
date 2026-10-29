"""Тесты безопасного адаптера PythonRouter."""

import unittest

from router.adapter import RouterAdapter
from router.registry import Agent, AgentRegistry
from router.service import RouterService
from router.task import TaskStatus


class TestRouterAdapter(unittest.TestCase):

    def setUp(self):
        self.registry = AgentRegistry()

        self.agent = Agent(
            agent_id="general_agent",
            name="General Agent",
            role="Тестовый исполнитель",
            capabilities=("general",),
        )

        self.registry.register(self.agent)

        self.service = RouterService(
            registry=self.registry,
            handlers={
                "general_agent": (
                    lambda task, agent: "Тестовая задача выполнена"
                ),
            },
        )

        self.adapter = RouterAdapter(self.service)

    def test_successful_execution(self):
        result = self.adapter.execute(
            "Выполнить тестовую задачу",
            ("general",),
        )

        self.assertTrue(result.success)
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.result, "Тестовая задача выполнена")
        self.assertEqual(result.agent_id, "general_agent")
        self.assertIsNotNone(result.task_id)

    def test_no_matching_agent(self):
        result = self.adapter.execute(
            "Найти специализированного агента",
            ("unknown",),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.status, TaskStatus.CREATED)
        self.assertIsNone(result.agent_id)
        self.assertIsNone(result.result)

    def test_missing_handler(self):
        service = RouterService(self.registry, {})
        adapter = RouterAdapter(service)

        result = adapter.execute(
            "Проверить отсутствие обработчика",
            ("general",),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.status, TaskStatus.FAILED)
        self.assertIn("не зарегистрирован обработчик", result.message)

    def test_handler_exception(self):
        def failing_handler(task, agent):
            raise RuntimeError("Ошибка тестового обработчика")

        service = RouterService(
            self.registry,
            {"general_agent": failing_handler},
        )

        result = RouterAdapter(service).execute(
            "Проверить ошибку",
            ("general",),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.status, TaskStatus.FAILED)
        self.assertIn("Ошибка тестового обработчика", result.message)

    def test_empty_handler_result(self):
        service = RouterService(
            self.registry,
            {"general_agent": lambda task, agent: "   "},
        )

        result = RouterAdapter(service).execute(
            "Проверить пустой результат",
            ("general",),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.status, TaskStatus.FAILED)
        self.assertIsNone(result.result)

    def test_empty_description(self):
        result = self.adapter.execute("   ", ("general",))

        self.assertFalse(result.success)
        self.assertIsNone(result.task_id)
        self.assertIsNone(result.status)

    def test_invalid_description_type(self):
        result = self.adapter.execute(None, ("general",))

        self.assertFalse(result.success)
        self.assertIsNone(result.task_id)

    def test_empty_capabilities(self):
        result = self.adapter.execute(
            "Проверить отсутствие возможностей",
            (),
        )

        self.assertFalse(result.success)
        self.assertIsNone(result.task_id)

    def test_invalid_capabilities(self):
        result = self.adapter.execute(
            "Проверить некорректные возможности",
            ("general", None),
        )

        self.assertFalse(result.success)
        self.assertIsNone(result.task_id)


if __name__ == "__main__":
    unittest.main()
