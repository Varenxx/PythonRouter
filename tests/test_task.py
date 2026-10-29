"""Автоматические тесты модели задач PythonRouter."""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from router.task import Task, TaskStatus


class TestTask(unittest.TestCase):

    def setUp(self) -> None:
        self.task = Task(
            description="  Написать Python-скрипт  ",
            required_capabilities=(" Python ", "coding"),
        )

    def test_task_creation(self) -> None:
        self.assertTrue(self.task.task_id)
        self.assertEqual(
            self.task.description,
            "Написать Python-скрипт",
        )
        self.assertEqual(
            self.task.required_capabilities,
            ("python", "coding"),
        )
        self.assertEqual(self.task.status, TaskStatus.CREATED)

    def test_assign_task(self) -> None:
        self.task.assign(" python_dev ")

        self.assertEqual(self.task.assigned_agent_id, "python_dev")
        self.assertEqual(self.task.status, TaskStatus.ASSIGNED)

    def test_complete_task_successfully(self) -> None:
        self.task.assign("python_dev")
        self.task.start()
        self.task.complete("  Скрипт готов  ")

        self.assertEqual(self.task.status, TaskStatus.COMPLETED)
        self.assertEqual(self.task.result, "Скрипт готов")
        self.assertIsNone(self.task.error)

    def test_fail_task(self) -> None:
        self.task.assign("python_dev")
        self.task.start()
        self.task.fail("Ошибка выполнения")

        self.assertEqual(self.task.status, TaskStatus.FAILED)
        self.assertEqual(self.task.error, "Ошибка выполнения")
        self.assertIsNone(self.task.result)

    def test_empty_description_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Task(
                description="   ",
                required_capabilities=("python",),
            )

    def test_empty_capabilities_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            Task(
                description="Проверить код",
                required_capabilities=("", "   "),
            )

    def test_empty_agent_id_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.task.assign("   ")

    def test_invalid_status_transition_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.task.start()

        self.task.assign("python_dev")
        self.task.start()

        with self.assertRaises(ValueError):
            self.task.assign("researcher")

    def test_empty_result_is_rejected(self) -> None:
        self.task.assign("python_dev")
        self.task.start()

        with self.assertRaises(ValueError):
            self.task.complete("   ")

        self.assertEqual(self.task.status, TaskStatus.RUNNING)

    def test_empty_error_is_rejected(self) -> None:
        self.task.assign("python_dev")
        self.task.start()

        with self.assertRaises(ValueError):
            self.task.fail("   ")

        self.assertEqual(self.task.status, TaskStatus.RUNNING)


if __name__ == "__main__":
    unittest.main(verbosity=2)