"""Автоматические тесты реестра PythonRouter."""

import sys
import unittest
from pathlib import Path

# Добавляем корень проекта в путь поиска модулей.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from router.registry import Agent, AgentRegistry


class TestAgentRegistry(unittest.TestCase):

    def setUp(self) -> None:
        self.registry = AgentRegistry()

        self.python_agent = Agent(
            agent_id="python_dev",
            name="Python-разработчик",
            role="Разработка и проверка Python-кода",
            capabilities=("python", "coding", "debugging"),
        )

        self.research_agent = Agent(
            agent_id="researcher",
            name="Исследователь",
            role="Исследование информации",
            capabilities=("research", "analysis"),
        )

    def test_register_agent(self) -> None:
        self.registry.register(self.python_agent)

        agent = self.registry.get("python_dev")

        self.assertIsNotNone(agent)
        self.assertEqual(agent.name, "Python-разработчик")

    def test_find_by_capability(self) -> None:
        self.registry.register(self.python_agent)
        self.registry.register(self.research_agent)

        results = self.registry.find_by_capability("python")

        self.assertEqual(
            [agent.agent_id for agent in results],
            ["python_dev"],
        )

    def test_disabled_agent_is_not_found_by_capability(self) -> None:
        self.registry.register(self.python_agent)

        self.assertTrue(self.registry.disable("python_dev"))
        self.assertEqual(
            self.registry.find_by_capability("python"),
            [],
        )

    def test_remove_agent(self) -> None:
        self.registry.register(self.python_agent)

        self.assertTrue(self.registry.remove("python_dev"))
        self.assertIsNone(self.registry.get("python_dev"))

    def test_duplicate_id_is_rejected(self) -> None:
        self.registry.register(self.python_agent)

        with self.assertRaises(ValueError):
            self.registry.register(self.python_agent)

    def test_empty_capability_is_rejected(self) -> None:
        invalid_agent = Agent(
            agent_id="invalid",
            name="Некорректный агент",
            role="Тест",
            capabilities=("", "   "),
        )

        with self.assertRaises(ValueError):
            self.registry.register(invalid_agent)


if __name__ == "__main__":
    unittest.main(verbosity=2)