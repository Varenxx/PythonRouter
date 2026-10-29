"""Модель задачи для PythonRouter."""

from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


class TaskStatus(str, Enum):
    """Допустимые состояния задачи."""

    CREATED = "created"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    """Задача, которую PythonRouter должен распределить между агентами."""

    description: str
    required_capabilities: tuple[str, ...]
    task_id: str = field(default_factory=lambda: str(uuid4()))
    status: TaskStatus = TaskStatus.CREATED
    assigned_agent_id: str | None = None
    result: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        """Проверяет и нормализует исходные данные задачи."""

        self.description = self.description.strip()

        if not self.description:
            raise ValueError("Описание задачи не может быть пустым.")

        self.task_id = self.task_id.strip()

        if not self.task_id:
            raise ValueError("ID задачи не может быть пустым.")

        if not isinstance(self.status, TaskStatus):
            raise ValueError("Недопустимый статус задачи.")

        normalized_capabilities = tuple(
            capability.strip().casefold()
            for capability in self.required_capabilities
            if isinstance(capability, str) and capability.strip()
        )

        if not normalized_capabilities:
            raise ValueError(
                "У задачи должна быть хотя бы одна необходимая возможность."
            )

        self.required_capabilities = normalized_capabilities

    def assign(self, agent_id: str) -> None:
        """Назначает задачу агенту."""

        if self.status != TaskStatus.CREATED:
            raise ValueError(
                "Назначить можно только созданную задачу."
            )

        normalized_agent_id = agent_id.strip()

        if not normalized_agent_id:
            raise ValueError("ID агента не может быть пустым.")

        self.assigned_agent_id = normalized_agent_id
        self.status = TaskStatus.ASSIGNED

    def start(self) -> None:
        """Переводит назначенную задачу в состояние выполнения."""

        if self.status != TaskStatus.ASSIGNED:
            raise ValueError(
                "Начать можно только назначенную задачу."
            )

        self.status = TaskStatus.RUNNING

    def complete(self, result: str) -> None:
        """Сохраняет результат и завершает задачу."""

        if self.status != TaskStatus.RUNNING:
            raise ValueError(
                "Завершить можно только выполняющуюся задачу."
            )

        normalized_result = result.strip()

        if not normalized_result:
            raise ValueError("Результат выполнения не может быть пустым.")

        self.result = normalized_result
        self.error = None
        self.status = TaskStatus.COMPLETED

    def fail(self, error: str) -> None:
        """Отмечает задачу как завершившуюся ошибкой."""

        if self.status not in (
            TaskStatus.ASSIGNED,
            TaskStatus.RUNNING,
        ):
            raise ValueError(
                "Ошибка допустима только для назначенной "
                "или выполняющейся задачи."
            )

        normalized_error = error.strip()

        if not normalized_error:
            raise ValueError("Описание ошибки не может быть пустым.")

        self.error = normalized_error
        self.result = None
        self.status = TaskStatus.FAILED