"""Тесты назначения задач через TaskDispatcher."""

import unittest

from router.registry import Agent, AgentRegistry
from router.task import Task, TaskStatus
from router.dispatcher import TaskDispatcher


class TestTaskDispatcher(unittest.TestCase):
    """Проверяет назначение задач специализированным агентам."""

    def setUp(self) -> None:
        self.registry = AgentRegistry()

        self.registry.register(
            Agent(
                agent_id="python_dev",
                name="Python-разработчик",
                role="Разработка и исправление кода",
                capabilities=("python", "coding"),
            )
        )

        self.registry.register(
            Agent(
                agent_id="researcher",
                name="Исследователь",
                role="Поиск и анализ информации",
                capabilities=("research", "analysis"),
            )
        )

        self.registry.register(
            Agent(
                agent_id="security_dev",
                name="Специалист по безопасности",
                role="Код и безопасность",
                capabilities=("python", "security"),
            )
        )

        self.dispatcher = TaskDispatcher(self.registry)

    def test_assigns_task_to_matching_agent(self) -> None:
        task = Task(
            description="Написать Python-скрипт",
            required_capabilities=("python",),
        )

        result = self.dispatcher.dispatch_task(task)

        self.assertTrue(result.success)
        self.assertEqual(result.agent.agent_id, "python_dev")
        self.assertEqual(task.assigned_agent_id, "python_dev")
        self.assertEqual(task.status, TaskStatus.ASSIGNED)

    def test_requires_agent_with_all_capabilities(self) -> None:
        task = Task(
            description="Написать безопасный Python-скрипт",
            required_capabilities=("python", "security"),
        )

        result = self.dispatcher.dispatch_task(task)

        self.assertTrue(result.success)
        self.assertEqual(result.agent.agent_id, "security_dev")
        self.assertEqual(task.assigned_agent_id, "security_dev")
        self.assertEqual(task.status, TaskStatus.ASSIGNED)

    def test_fails_when_no_agent_has_all_capabilities(self) -> None:
        task = Task(
            description="Исследовать и написать код",
            required_capabilities=("research", "python"),
        )

        result = self.dispatcher.dispatch_task(task)

        self.assertFalse(result.success)
        self.assertIsNone(result.agent)
        self.assertIsNone(task.assigned_agent_id)
        self.assertEqual(task.status, TaskStatus.CREATED)

    def test_does_not_assign_task_to_disabled_agent(self) -> None:
        self.registry.disable("python_dev")

        task = Task(
            description="Написать Python-скрипт",
            required_capabilities=("python", "coding"),
        )

        result = self.dispatcher.dispatch_task(task)

        self.assertFalse(result.success)
        self.assertIsNone(result.agent)
        self.assertIsNone(task.assigned_agent_id)
        self.assertEqual(task.status, TaskStatus.CREATED)

    def test_rejects_already_assigned_task(self) -> None:
        task = Task(
            description="Написать Python-скрипт",
            required_capabilities=("python",),
        )
        task.assign("python_dev")

        result = self.dispatcher.dispatch_task(task)

        self.assertFalse(result.success)
        self.assertIsNone(result.agent)
        self.assertEqual(task.assigned_agent_id, "python_dev")
        self.assertEqual(task.status, TaskStatus.ASSIGNED)

    def test_rejects_completed_task(self) -> None:
        task = Task(
            description="Написать Python-скрипт",
            required_capabilities=("python",),
        )
        task.assign("python_dev")
        task.start()
        task.complete("Скрипт готов.")

        result = self.dispatcher.dispatch_task(task)

        self.assertFalse(result.success)
        self.assertEqual(task.status, TaskStatus.COMPLETED)
        self.assertEqual(task.result, "Скрипт готов.")

    def test_normalizes_task_capabilities(self) -> None:
        task = Task(
            description="Проверить код",
            required_capabilities=(" Python ", " SECURITY "),
        )

        result = self.dispatcher.dispatch_task(task)

        self.assertTrue(result.success)
        self.assertEqual(result.agent.agent_id, "security_dev")

    def test_reports_required_capabilities(self) -> None:
        task = Task(
            description="Выполнить специальную задачу",
            required_capabilities=("unknown_capability",),
        )

        result = self.dispatcher.dispatch_task(task)

        self.assertFalse(result.success)
        self.assertIn("unknown_capability", result.message)


if __name__ == "__main__":
    unittest.main()