"""Изолированная демонстрационная интеграция PythonRouter."""

from router.adapter import AdapterResult, RouterAdapter
from router.registry import Agent, AgentRegistry
from router.service import RouterService


def demo_handler(task, agent) -> str:
    """Безопасный обработчик без внешних действий."""
    return (
        f"Демонстрационная задача принята агентом '{agent.name}'. "
        f"Описание: {task.description}"
    )


def create_demo_adapter() -> RouterAdapter:
    """Создать адаптер с демонстрационным агентом."""

    registry = AgentRegistry()

    registry.register(
        Agent(
            agent_id="demo_agent",
            name="Demo Agent",
            role="Демонстрационный исполнитель",
            capabilities=("demo",),
        )
    )

    service = RouterService(
        registry=registry,
        handlers={
            "demo_agent": demo_handler,
        },
    )

    return RouterAdapter(service)


def execute_demo_task(description: str) -> AdapterResult:
    """Выполнить демонстрационную задачу через адаптер."""
    adapter = create_demo_adapter()

    return adapter.execute(
        description=description,
        required_capabilities=("demo",),
    )
