"""Маршрутизация задач между специализированными агентами."""

from dataclasses import dataclass

from router.registry import Agent, AgentRegistry
from router.task import Task, TaskStatus


@dataclass(frozen=True)
class RoutingResult:
    """Результат выбора исполнителя для задачи."""

    task: str
    capability: str
    agent: Agent | None
    success: bool
    message: str


class TaskDispatcher:
    """Подбирает исполнителей для отдельных задач."""

    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry

    def dispatch(
        self,
        task: str,
        capability: str,
    ) -> RoutingResult:
        """Выбирает агента по одной возможности.

        Сохраняет совместимость с прежним интерфейсом.
        """

        normalized_task = task.strip()
        normalized_capability = capability.strip().casefold()

        if not normalized_task:
            return RoutingResult(
                task=task,
                capability=normalized_capability,
                agent=None,
                success=False,
                message="Описание задачи не может быть пустым.",
            )

        if not normalized_capability:
            return RoutingResult(
                task=normalized_task,
                capability=normalized_capability,
                agent=None,
                success=False,
                message="Не указана необходимая возможность.",
            )

        candidates = self.registry.find_by_capability(
            normalized_capability
        )

        if not candidates:
            return RoutingResult(
                task=normalized_task,
                capability=normalized_capability,
                agent=None,
                success=False,
                message=(
                    "Не найден включённый агент "
                    f"с возможностью '{normalized_capability}'."
                ),
            )

        selected_agent = candidates[0]

        return RoutingResult(
            task=normalized_task,
            capability=normalized_capability,
            agent=selected_agent,
            success=True,
            message=(
                f"Для задачи выбран агент: {selected_agent.name}."
            ),
        )

    def dispatch_task(self, task: Task) -> RoutingResult:
        """Назначает задачу агенту со всеми нужными возможностями."""

        capability = ", ".join(task.required_capabilities)

        if task.status != TaskStatus.CREATED:
            return RoutingResult(
                task=task.description,
                capability=capability,
                agent=None,
                success=False,
                message=(
                    "Назначить можно только задачу "
                    "со статусом CREATED."
                ),
            )

        candidates = [
            agent
            for agent in self.registry.list_agents()
            if agent.enabled
            and all(
                required in agent.capabilities
                for required in task.required_capabilities
            )
        ]

        if not candidates:
            return RoutingResult(
                task=task.description,
                capability=capability,
                agent=None,
                success=False,
                message=(
                    "Не найден включённый агент, "
                    "который поддерживает все необходимые возможности: "
                    f"{capability}."
                ),
            )

        selected_agent = candidates[0]
        task.assign(selected_agent.agent_id)

        return RoutingResult(
            task=task.description,
            capability=capability,
            agent=selected_agent,
            success=True,
            message=(
                f"Задача назначена агенту: {selected_agent.name}."
            ),
        )