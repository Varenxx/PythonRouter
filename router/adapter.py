"""Безопасный адаптер между главным помощником и RouterService."""

from dataclasses import dataclass

from router.registry import Agent
from router.service import RouterService
from router.task import TaskStatus


@dataclass(frozen=True)
class AdapterResult:
    """Результат выполнения задачи для главного помощника."""

    success: bool
    task_id: str | None
    status: TaskStatus | None
    message: str
    result: str | None = None
    agent_id: str | None = None


class RouterAdapter:
    """Предоставляет простой интерфейс к RouterService."""

    def __init__(self, service: RouterService) -> None:
        self._service = service

    def list_agents(self) -> list[Agent]:
        """Вернуть список зарегистрированных агентов через сервис."""
        return self._service.list_agents()

    def execute(
        self,
        description: str,
        required_capabilities: tuple[str, ...],
    ) -> AdapterResult:
        """Передаёт задачу сервису и преобразует результат."""

        if not isinstance(description, str) or not description.strip():
            return AdapterResult(
                success=False,
                task_id=None,
                status=None,
                message="Описание задачи не может быть пустым.",
            )

        if (
            not isinstance(required_capabilities, tuple)
            or not required_capabilities
            or any(
                not isinstance(capability, str)
                or not capability.strip()
                for capability in required_capabilities
            )
        ):
            return AdapterResult(
                success=False,
                task_id=None,
                status=None,
                message="Необходимо указать возможности агента.",
            )

        service_result = self._service.run_task(
            description=description,
            required_capabilities=required_capabilities,
        )

        task = service_result.task

        return AdapterResult(
            success=service_result.success,
            task_id=task.task_id,
            status=task.status,
            message=service_result.message,
            result=task.result,
            agent_id=(
                service_result.agent.agent_id
                if service_result.agent is not None
                else None
            ),
        )
