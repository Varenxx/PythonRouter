"""Подключение Python-агента к маршрутизатору."""

from router.adapter import AdapterResult, RouterAdapter
from router.python_agent import ChatClient, PythonAgentHandler
from router.registry import Agent, AgentRegistry
from router.service import RouterService


def create_python_adapter(client: ChatClient) -> RouterAdapter:
    """Создать адаптер Python-агента с предоставленным клиентом модели."""
    registry = AgentRegistry()

    registry.register(
        Agent(
            agent_id="python_agent",
            name="Python Agent",
            role="Помощник по разработке на Python",
            capabilities=("python",),
        )
    )

    service = RouterService(
        registry=registry,
        handlers={
            "python_agent": PythonAgentHandler(client),
        },
    )

    return RouterAdapter(service)


def execute_python_task(
    description: str,
    client: ChatClient,
) -> AdapterResult:
    """Передать задачу Python-агенту и вернуть результат адаптера."""
    adapter = create_python_adapter(client)

    return adapter.execute(
        description=description,
        required_capabilities=("python",),
    )