"""Интеграционные тесты полного цикла PythonRouter."""

import unittest

from router.dispatcher import TaskDispatcher
from router.executor import TaskExecutor
from router.registry import Agent, AgentRegistry
from router.task import Task, TaskStatus


class TestPythonRouterIntegration(unittest.TestCase):

    def setUp(self):
        self.registry = AgentRegistry()
        self.agent = Agent(
            agent_id="general_agent",
            name="General Agent",
            role="Общий исполнитель",
            capabilities=("general",),
        )
        self.registry.register(self.agent)
        self.dispatcher = TaskDispatcher(self.registry)
        self.executor = TaskExecutor()

    def test_full_task_cycle(self):
        task = Task(
            description="Сколько будет 2 + 2?",
            required_capabilities=("general",),
        )

        routing = self.dispatcher.dispatch_task(task)

        self.assertTrue(routing.success)
        self.assertEqual(task.status, TaskStatus.ASSIGNED)
        self.assertEqual(task.assigned_agent_id, self.agent.agent_id)

        def fake_handler(received_task, received_agent):
            self.assertIs(received_task, task)
            self.assertEqual(received_agent.agent_id, self.agent.agent_id)
            return "4"

        result = self.executor.execute(task, self.agent, fake_handler)

        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.result, "4")
        self.assertIsNone(result.error)

    def test_task_fails_when_handler_raises(self):
        task = Task(
            description="Проверить обработку ошибки",
            required_capabilities=("general",),
        )
        self.dispatcher.dispatch_task(task)

        def failing_handler(received_task, received_agent):
            raise RuntimeError("Тестовая ошибка")

        result = self.executor.execute(
            task, self.agent, failing_handler
        )

        self.assertEqual(result.status, TaskStatus.FAILED)
        self.assertIsNone(result.result)
        self.assertIn("Тестовая ошибка", result.error)

    def test_task_fails_when_handler_returns_empty_text(self):
        task = Task(
            description="Проверить пустой ответ",
            required_capabilities=("general",),
        )
        self.dispatcher.dispatch_task(task)

        result = self.executor.execute(
            task,
            self.agent,
            lambda received_task, received_agent: "   ",
        )

        self.assertEqual(result.status, TaskStatus.FAILED)
        self.assertIsNone(result.result)
        self.assertIn("непустой текстовый результат", result.error)


if __name__ == "__main__":
    unittest.main()
