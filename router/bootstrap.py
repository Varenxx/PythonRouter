
"""Сборка общего маршрутизатора с демонстрационным и двумя AI-агентами."""

from router.adapter import RouterAdapter
from router.integration import demo_handler
from router.python_agent import ChatClient, PythonAgentHandler
from router.registry import Agent, AgentRegistry
from router.security_agent import SecurityAgentHandler
from router.service import RouterService


def create_router_adapter(python_client: ChatClient) -> RouterAdapter:
    """Создать общий адаптер с тремя агентами без обращения к модели."""
    registry = AgentRegistry()

    registry.register(
        Agent(
            agent_id="demo_agent",
            name="Demo Agent",
            role="Демонстрационный исполнитель",
            capabilities=("demo",),
        )
    )

    registry.register(
        Agent(
            agent_id="python_agent",
            name="Python Agent",
            role="Помощник по разработке на Python",
            capabilities=("python",),
        )
    )

    registry.register(
        Agent(
            agent_id="security_agent",
            name="Security Agent",
            role="Проверка безопасности Python-кода",
            capabilities=("security",),
        )
    )

    service = RouterService(
        registry=registry,
        handlers={
            "demo_agent": demo_handler,
            "python_agent": PythonAgentHandler(python_client),
            "security_agent": SecurityAgentHandler(python_client),
        },
    )

    return RouterAdapter(service)