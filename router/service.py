"""Сервис, объединяющий маршрутизацию и выполнение задач."""

from dataclasses import dataclass
from typing import Mapping

from router.dispatcher import TaskDispatcher
from router.executor import AgentHandler, TaskExecutor
from router.registry import Agent, AgentRegistry
from router.task import Task, TaskStatus


@dataclass(frozen=True)
class ServiceResult:
    """Результат обработки задачи сервисом."""

    task: Task
    success: bool
    message: str
    agent: Agent | None = None


class RouterService:
    """Координирует выбор агента и выполнение задачи."""

    def __init__(
        self,
        registry: AgentRegistry,
        handlers: Mapping[str, AgentHandler],
    ) -> None:
        self._registry = registry
        self._dispatcher = TaskDispatcher(registry)
        self._executor = TaskExecutor()
        self._handlers = dict(handlers)

    def list_agents(self) -> list[Agent]:
        """Вернуть список всех агентов, включая отключённых."""
        return self._registry.list_agents()

    def run_task(
        self,
        description: str,
        required_capabilities: tuple[str, ...],
    ) -> ServiceResult:
        """Маршрутизирует задачу, выполняет её и возвращает результат."""

        task = Task(
            description=description,
            required_capabilities=required_capabilities,
        )

        routing = self._dispatcher.dispatch_task(task)

        if not routing.success or routing.agent is None:
            return ServiceResult(
                task=task,
                success=False,
                message=routing.message,
            )

        agent = routing.agent
        handler = self._handlers.get(agent.agent_id)

        if handler is None:
            message = (
                f"Для агента '{agent.agent_id}' "
                "не зарегистрирован обработчик."
            )
            task.fail(message)

            return ServiceResult(
                task=task,
                success=False,
                message=message,
                agent=agent,
            )

        result_task = self._executor.execute(task, agent, handler)

        if result_task.status == TaskStatus.COMPLETED:
            return ServiceResult(
                task=result_task,
                success=True,
                message=f"Задача выполнена агентом '{agent.agent_id}'.",
                agent=agent,
            )

        error_message = (
            result_task.error
            or f"Задача завершилась со статусом '{result_task.status.value}'."
        )

        return ServiceResult(
            task=result_task,
            success=False,
            message=error_message,
            agent=agent,
        )
