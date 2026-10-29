"""Тесты демонстрационной интеграции PythonRouter."""

import unittest

from router.integration import (
    create_demo_adapter,
    execute_demo_task,
)
from router.task import TaskStatus


class TestDemoIntegration(unittest.TestCase):

    def test_successful_execution(self):
        result = execute_demo_task("Проверить выполнение")

        self.assertTrue(result.success)
        self.assertEqual(result.status, TaskStatus.COMPLETED)

    def test_correct_agent(self):
        result = execute_demo_task("Проверить выбор агента")

        self.assertEqual(result.agent_id, "demo_agent")

    def test_result_content(self):
        result = execute_demo_task("Уникальное описание задачи")

        self.assertIn("Demo Agent", result.result)
        self.assertIn("Уникальное описание задачи", result.result)

    def test_unique_task_ids(self):
        first = execute_demo_task("Первая задача")
        second = execute_demo_task("Вторая задача")

        self.assertNotEqual(first.task_id, second.task_id)

    def test_empty_description(self):
        result = execute_demo_task("   ")

        self.assertFalse(result.success)
        self.assertIsNone(result.task_id)
        self.assertIsNone(result.status)

    def test_no_matching_capability(self):
        adapter = create_demo_adapter()

        result = adapter.execute(
            description="Проверить неизвестную возможность",
            required_capabilities=("unknown",),
        )

        self.assertFalse(result.success)
        self.assertEqual(result.status, TaskStatus.CREATED)
        self.assertIsNone(result.agent_id)


if __name__ == "__main__":
    unittest.main()
