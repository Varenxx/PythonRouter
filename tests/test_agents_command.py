
"""Проверки команды «агенты» без модели, выполнения задач и SQLite."""

import importlib
import io
import unittest
from contextlib import ExitStack, redirect_stdout
from unittest.mock import Mock, call, patch

from router.adapter import RouterAdapter
from router.bootstrap import create_router_adapter
from router.commands import handle_agent_command
from router.python_agent import ChatClient
from router.registry import Agent, AgentRegistry
from router.service import RouterService


class TestAgentsCommand(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)

        for target in (
            "sqlite3.connect",
            "urllib.request.urlopen",
            "router.ollama_client.urlopen",
            "router.executor.TaskExecutor.execute",
            "router.commands.execute_demo_task",
            "router.commands.execute_python_task",
            "router.commands.OllamaClient",
        ):
            blocker = self.stack.enter_context(
                patch(
                    target,
                    side_effect=AssertionError(
                        f"Команда «агенты» не должна вызывать: {target}"
                    ),
                )
            )
            self.addCleanup(blocker.assert_not_called)

        self.client = Mock(spec=ChatClient)
        self.client.chat.side_effect = AssertionError(
            "Для списка агентов модель не нужна."
        )
        self.addCleanup(self.client.chat.assert_not_called)
        self.adapter = create_router_adapter(self.client)

    def test_lists_agents_from_shared_registry(self):
        answer = handle_agent_command(
            "агенты",
            router_adapter=self.adapter,
        )

        self.assertTrue(answer.startswith("Зарегистрированные агенты:"))
        self.assertIn(
            "ID: demo_agent\n"
            "Название: Demo Agent\n"
            "Возможности: demo\n"
            "Состояние: включён",
            answer,
        )
        self.assertIn(
            "ID: python_agent\n"
            "Название: Python Agent\n"
            "Возможности: python\n"
            "Состояние: включён",
            answer,
        )
        self.assertIn(
            "ID: security_agent\n"
            "Название: Security Agent\n"
            "Возможности: security\n"
            "Состояние: включён",
            answer,
        )
        self.assertEqual(answer.count("ID: "), 3)

    def test_empty_registry_has_clear_message(self):
        adapter = RouterAdapter(
            RouterService(registry=AgentRegistry(), handlers={})
        )

        answer = handle_agent_command(
            "агенты",
            router_adapter=adapter,
        )

        self.assertEqual(answer, "В реестре пока нет агентов.")

    def test_disabled_agent_and_multiple_capabilities_are_displayed(self):
        registry = AgentRegistry()
        registry.register(
            Agent(
                agent_id="custom_agent",
                name="Custom Agent",
                role="Тестовый специалист",
                capabilities=("python", "review"),
                enabled=False,
            )
        )
        adapter = RouterAdapter(
            RouterService(registry=registry, handlers={})
        )

        answer = handle_agent_command(
            "агенты",
            router_adapter=adapter,
        )

        self.assertIn("ID: custom_agent", answer)
        self.assertIn("Название: Custom Agent", answer)
        self.assertIn("Возможности: python, review", answer)
        self.assertIn("Состояние: отключён", answer)
        self.assertNotIn("demo_agent", answer)

    def test_uppercase_and_surrounding_whitespace_are_accepted(self):
        expected = handle_agent_command(
            "агенты",
            router_adapter=self.adapter,
        )

        answer = handle_agent_command(
            "  АГЕНТЫ \n\t ",
            router_adapter=self.adapter,
        )

        self.assertEqual(answer, expected)

    def test_missing_shared_adapter_returns_error(self):
        expected = (
            "Ошибка: для команды 'агенты' "
            "необходим общий маршрутизатор."
        )

        self.assertEqual(handle_agent_command("агенты"), expected)
        self.assertEqual(
            handle_agent_command("агенты", python_client=self.client),
            expected,
        )

    def test_similar_text_is_not_treated_as_listing_command(self):
        with patch.object(
            self.adapter,
            "list_agents",
            side_effect=AssertionError(
                "Похожий текст не должен запрашивать список."
            ),
        ) as listing:
            for prompt in (
                "агент",
                "агенты:",
                "агенты покажи",
                "Покажи агентов",
            ):
                with self.subTest(prompt=prompt):
                    self.assertIsNone(
                        handle_agent_command(
                            prompt,
                            router_adapter=self.adapter,
                        )
                    )

            listing.assert_not_called()

    def test_main_displays_and_saves_listing_without_model_call(self):
        app = importlib.import_module("main")
        session_id = "agents-listing-test-session"
        conversation = [
            {"role": "system", "content": app.SYSTEM_PROMPT}
        ]
        output = io.StringIO()

        with ExitStack() as local:
            mocks = {}
            for name in (
                "init_db",
                "init_memory",
                "save_message",
                "load_messages",
                "list_sessions",
                "list_memories",
                "add_memory",
                "delete_memory",
                "choose_session",
                "ask_local_model",
            ):
                mocks[name] = local.enter_context(
                    patch.object(app, name, autospec=True)
                )

            mocks["choose_session"].return_value = (
                session_id,
                conversation,
            )
            mocks["list_memories"].return_value = []
            mocks["ask_local_model"].side_effect = AssertionError(
                "Список агентов не должен передаваться обычному чату."
            )

            client_factory = local.enter_context(
                patch.object(
                    app,
                    "OllamaClient",
                    autospec=True,
                    return_value=self.client,
                )
            )
            local.enter_context(
                patch(
                    "builtins.input",
                    side_effect=["агенты", "выход"],
                )
            )
            local.enter_context(redirect_stdout(output))

            app.main()

            client_factory.assert_called_once_with(model=app.MODEL)
            mocks["init_db"].assert_called_once_with()
            mocks["init_memory"].assert_called_once_with()
            mocks["ask_local_model"].assert_not_called()

            self.assertEqual(len(conversation), 3)
            self.assertEqual(
                conversation[1],
                {"role": "user", "content": "агенты"},
            )
            self.assertEqual(conversation[2]["role"], "assistant")

            answer = conversation[2]["content"]
            self.assertTrue(
                answer.startswith("Зарегистрированные агенты:")
            )
            self.assertIn("ID: demo_agent", answer)
            self.assertIn("ID: python_agent", answer)
            self.assertIn("ID: security_agent", answer)
            self.assertIn("Возможности: security", answer)
            self.assertEqual(answer.count("ID: "), 3)
            self.assertIn(answer, output.getvalue())

            self.assertEqual(
                mocks["save_message"].call_args_list,
                [
                    call(session_id, "user", "агенты"),
                    call(session_id, "assistant", answer),
                ],
            )


if __name__ == "__main__":
    unittest.main()
