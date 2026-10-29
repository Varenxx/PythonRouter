"""Тесты сервиса маршрутизации и выполнения задач."""

import unittest

from router.registry import Agent, AgentRegistry
from router.service import RouterService
from router.task import TaskStatus


class TestRouterService(unittest.TestCase):

    def setUp(self):
        self.registry = AgentRegistry()
        self.agent = Agent(
            agent_id="general_agent",
            name="General Agent",
            role="Общий исполнитель",
            capabilities=("general",),
        )
        self.registry.register(self.agent)

        self.service = RouterService(
            registry=self.registry,
            handlers={
                "general_agent": (
                    lambda task, agent: "Задача выполнена"
                ),
            },
        )

    def test_successful_task_execution(self):
        result = self.service.run_task(
            description="Проверить успешное выполнение",
            required_capabilities=("general",),
        )

        self.assertTrue(result.success)
        self.assertEqual(result.task.status, TaskStatus.COMPLETED)
        self.assertEqual(result.task.result, "Задача выполнена")
        self.assertIsNone(result.task.error)
        self.assertEqual(result.agent.agent_id, "general_agent")

    def test_no_matching_agent(self):
        result = self.service.run_task(
            description="Задача без подходящего исполнителя",
            required_capabilities=("unknown_capability",),
        )

        self.assertFalse(result.success)
        self.assertIsNone(result.agent)
        self.assertEqual(result.task.status, TaskStatus.CREATED)
        self.assertIsNotNone(result.message)

    def test_missing_handler(self):
        service = RouterService(
            registry=self.registry,
            handlers={},
        )

        result = service.run_task(
            description="Проверить отсутствие обработчика",
            required_capabilities=("general",),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.task.status, TaskStatus.FAILED)
        self.assertIn("не зарегистрирован обработчик", result.message)
        self.assertIsNotNone(result.agent)

    def test_handler_exception(self):
        def failing_handler(task, agent):
            raise RuntimeError("Тестовая ошибка обработчика")

        service = RouterService(
            registry=self.registry,
            handlers={"general_agent": failing_handler},
        )

        result = service.run_task(
            description="Проверить ошибку обработчика",
            required_capabilities=("general",),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.task.status, TaskStatus.FAILED)
        self.assertIn("Тестовая ошибка обработчика", result.message)
        self.assertIsNotNone(result.task.error)

    def test_empty_handler_result(self):
        service = RouterService(
            registry=self.registry,
            handlers={"general_agent": lambda task, agent: "   "},
        )

        result = service.run_task(
            description="Проверить пустой результат",
            required_capabilities=("general",),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.task.status, TaskStatus.FAILED)
        self.assertIsNotNone(result.task.error)


if __name__ == "__main__":
    unittest.main()