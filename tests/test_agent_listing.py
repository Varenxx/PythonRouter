
"""Проверки получения списка агентов без выполнения задач."""

import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

from router.adapter import RouterAdapter
from router.bootstrap import create_router_adapter
from router.python_agent import ChatClient
from router.registry import Agent, AgentRegistry
from router.service import RouterService


class TestAgentListing(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)

        for target in (
            "sqlite3.connect",
            "urllib.request.urlopen",
            "router.ollama_client.urlopen",
            "router.executor.TaskExecutor.execute",
        ):
            blocker = self.stack.enter_context(
                patch(
                    target,
                    side_effect=AssertionError(
                        f"Получение списка не должно вызывать: {target}"
                    ),
                )
            )
            self.addCleanup(blocker.assert_not_called)

        self.registry = AgentRegistry()
        self.service = RouterService(
            registry=self.registry,
            handlers={},
        )
        self.adapter = RouterAdapter(self.service)

        self.python_agent = Agent(
            agent_id="python_agent",
            name="Python Agent",
            role="Помощник по разработке на Python",
            capabilities=("python",),
        )
        self.demo_agent = Agent(
            agent_id="demo_agent",
            name="Demo Agent",
            role="Демонстрационный исполнитель",
            capabilities=("demo",),
        )

    def test_empty_registry_returns_empty_lists(self):
        self.assertEqual(self.service.list_agents(), [])
        self.assertEqual(self.adapter.list_agents(), [])

    def test_bootstrap_lists_three_agents_without_calling_model(self):
        client = Mock(spec=ChatClient)
        client.chat.side_effect = AssertionError(
            "Для получения списка модель не нужна."
        )
        adapter = create_router_adapter(client)

        agents = adapter.list_agents()
        by_id = {agent.agent_id: agent for agent in agents}

        self.assertEqual(len(agents), 3)
        self.assertEqual(
            set(by_id),
            {"demo_agent", "python_agent", "security_agent"},
        )

        self.assertEqual(by_id["demo_agent"].name, "Demo Agent")
        self.assertEqual(
            by_id["demo_agent"].capabilities,
            ("demo",),
        )
        self.assertTrue(by_id["demo_agent"].enabled)

        self.assertEqual(by_id["python_agent"].name, "Python Agent")
        self.assertEqual(
            by_id["python_agent"].capabilities,
            ("python",),
        )
        self.assertTrue(by_id["python_agent"].enabled)

        self.assertEqual(
            by_id["security_agent"].name,
            "Security Agent",
        )
        self.assertEqual(
            by_id["security_agent"].capabilities,
            ("security",),
        )
        self.assertTrue(by_id["security_agent"].enabled)

        client.chat.assert_not_called()

    def test_disabled_agent_remains_visible_and_state_is_current(self):
        self.registry.register(self.python_agent)
        self.registry.disable("python_agent")

        for source in (self.service, self.adapter):
            with self.subTest(source=type(source).__name__, enabled=False):
                agents = source.list_agents()
                self.assertEqual(len(agents), 1)
                self.assertEqual(agents[0].agent_id, "python_agent")
                self.assertFalse(agents[0].enabled)

        self.registry.enable("python_agent")

        for source in (self.service, self.adapter):
            with self.subTest(source=type(source).__name__, enabled=True):
                agents = source.list_agents()
                self.assertEqual(len(agents), 1)
                self.assertEqual(agents[0].agent_id, "python_agent")
                self.assertTrue(agents[0].enabled)

    def test_listing_reflects_registration_and_removal(self):
        self.registry.register(self.demo_agent)

        self.assertEqual(
            [agent.agent_id for agent in self.adapter.list_agents()],
            ["demo_agent"],
        )

        self.registry.register(self.python_agent)

        for source in (self.service, self.adapter):
            with self.subTest(source=type(source).__name__, stage="added"):
                self.assertEqual(
                    {agent.agent_id for agent in source.list_agents()},
                    {"demo_agent", "python_agent"},
                )

        self.registry.remove("demo_agent")

        for source in (self.service, self.adapter):
            with self.subTest(source=type(source).__name__, stage="removed"):
                self.assertEqual(
                    [agent.agent_id for agent in source.list_agents()],
                    ["python_agent"],
                )

    def test_modifying_returned_list_does_not_change_registry(self):
        self.registry.register(self.python_agent)

        for source in (self.service, self.adapter):
            with self.subTest(source=type(source).__name__):
                agents = source.list_agents()
                agents.clear()
                agents.append(self.demo_agent)

                self.assertEqual(
                    self.registry.list_agents(),
                    [self.python_agent],
                )
                self.assertEqual(
                    source.list_agents(),
                    [self.python_agent],
                )


if __name__ == "__main__":
    unittest.main()
