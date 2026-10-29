"""Тесты исполнителя задач PythonRouter."""

import unittest

from router.dispatcher import TaskDispatcher
from router.executor import TaskExecutor
from router.registry import Agent, AgentRegistry
from router.task import Task, TaskStatus


class TestTaskExecutor(unittest.TestCase):
    """Проверяет выполнение назначенных задач."""

    def setUp(self) -> None:
        self.registry = AgentRegistry()
        self.agent = Agent(
            agent_id="python_dev",
            name="Python-разработчик",
            role="Разработка кода",
            capabilities=("python", "coding"),
        )
        self.registry.register(self.agent)

        self.dispatcher = TaskDispatcher(self.registry)
        self.executor = TaskExecutor()

    def create_assigned_task(self) -> Task:
        """Создаёт задачу и назначает её зарегистрированному агенту."""

        task = Task(
            description="Написать тестовый скрипт",
            required_capabilities=("python",),
        )

        routing_result = self.dispatcher.dispatch_task(task)

        self.assertTrue(routing_result.success)
        return task

    def test_executes_task_successfully(self) -> None:
        task = self.create_assigned_task()

        def handler(task: Task, agent: Agent) -> str:
            return "Скрипт успешно создан."

        result = self.executor.execute(task, self.agent, handler)

        self.assertIs(result, task)
        self.assertEqual(result.status, TaskStatus.COMPLETED)
        self.assertEqual(result.result, "Скрипт успешно создан.")
        self.assertIsNone(result.error)

    def test_records_handler_error(self) -> None:
        task = self.create_assigned_task()

        def handler(task: Task, agent: Agent) -> str:
            raise RuntimeError("Тестовая ошибка агента")

        result = self.executor.execute(task, self.agent, handler)

        self.assertEqual(result.status, TaskStatus.FAILED)
        self.assertIsNone(result.result)
        self.assertIn("RuntimeError", result.error)
        self.assertIn("Тестовая ошибка агента", result.error)

    def test_rejects_empty_handler_result(self) -> None:
        task = self.create_assigned_task()

        def handler(task: Task, agent: Agent) -> str:
            return "   "

        result = self.executor.execute(task, self.agent, handler)

        self.assertEqual(result.status, TaskStatus.FAILED)
        self.assertIn("ValueError", result.error)

    def test_rejects_unassigned_task(self) -> None:
        task = Task(
            description="Не назначенная задача",
            required_capabilities=("python",),
        )

        with self.assertRaises(ValueError):
            self.executor.execute(
                task,
                self.agent,
                lambda task, agent: "Результат",
            )

        self.assertEqual(task.status, TaskStatus.CREATED)

    def test_rejects_wrong_agent(self) -> None:
        task = self.create_assigned_task()

        wrong_agent = Agent(
            agent_id="researcher",
            name="Исследователь",
            role="Анализ информации",
            capabilities=("research",),
        )

        with self.assertRaises(ValueError):
            self.executor.execute(
                task,
                wrong_agent,
                lambda task, agent: "Результат",
            )

        self.assertEqual(task.status, TaskStatus.ASSIGNED)

    def test_rejects_disabled_agent(self) -> None:
        task = self.create_assigned_task()
        self.registry.disable("python_dev")

        disabled_agent = self.registry.get("python_dev")
        self.assertIsNotNone(disabled_agent)

        with self.assertRaises(ValueError):
            self.executor.execute(
                task,
                disabled_agent,
                lambda task, agent: "Результат",
            )

        self.assertEqual(task.status, TaskStatus.ASSIGNED)

    def test_rejects_non_text_result(self) -> None:
        task = self.create_assigned_task()

        def handler(task: Task, agent: Agent) -> str:
            return None

        result = self.executor.execute(task, self.agent, handler)

        self.assertEqual(result.status, TaskStatus.FAILED)
        self.assertIn("ValueError", result.error)


if __name__ == "__main__":
    unittest.main()