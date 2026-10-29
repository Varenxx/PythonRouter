"""Автоматические тесты маршрутизатора PythonRouter."""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from router.registry import Agent, AgentRegistry
from router.dispatcher import TaskDispatcher


class TestTaskDispatcher(unittest.TestCase):

    def setUp(self) -> None:
        self.registry = AgentRegistry()

        self.python_agent = Agent(
            agent_id="python_dev",
            name="Python-разработчик",
            role="Разработка и отладка Python-кода",
            capabilities=("python", "coding", "debugging"),
        )

        self.research_agent = Agent(
            agent_id="researcher",
            name="Исследователь",
            role="Исследование и анализ информации",
            capabilities=("research", "analysis"),
        )

        self.registry.register(self.python_agent)
        self.registry.register(self.research_agent)

        self.dispatcher = TaskDispatcher(self.registry)

    def test_select_python_agent(self) -> None:
        result = self.dispatcher.dispatch(
            "Написать Python-скрипт",
            "python",
        )

        self.assertTrue(result.success)
        self.assertEqual(result.agent.agent_id, "python_dev")

    def test_select_research_agent(self) -> None:
        result = self.dispatcher.dispatch(
            "Изучить тему",
            "research",
        )

        self.assertTrue(result.success)
        self.assertEqual(result.agent.agent_id, "researcher")

    def test_disabled_agent_is_not_selected(self) -> None:
        self.registry.disable("python_dev")

        result = self.dispatcher.dispatch(
            "Написать Python-скрипт",
            "python",
        )

        self.assertFalse(result.success)
        self.assertIsNone(result.agent)

    def test_unknown_capability(self) -> None:
        result = self.dispatcher.dispatch(
            "Выполнить задачу",
            "unknown_skill",
        )

        self.assertFalse(result.success)
        self.assertIsNone(result.agent)

    def test_empty_task_is_rejected(self) -> None:
        result = self.dispatcher.dispatch(
            "   ",
            "python",
        )

        self.assertFalse(result.success)
        self.assertIsNone(result.agent)

    def test_empty_capability_is_rejected(self) -> None:
        result = self.dispatcher.dispatch(
            "Выполнить задачу",
            "   ",
        )

        self.assertFalse(result.success)
        self.assertIsNone(result.agent)


if __name__ == "__main__":
    unittest.main(verbosity=2)