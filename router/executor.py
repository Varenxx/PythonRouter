"""Выполнение задач назначенными агентами PythonRouter."""

from collections.abc import Callable

from router.registry import Agent
from router.task import Task, TaskStatus


AgentHandler = Callable[[Task, Agent], str]


class TaskExecutor:
    """Запускает обработчик агента и сохраняет результат задачи."""

    def execute(
        self,
        task: Task,
        agent: Agent,
        handler: AgentHandler,
    ) -> Task:
        """Выполняет назначенную задачу через обработчик агента."""

        if task.status != TaskStatus.ASSIGNED:
            raise ValueError(
                "Выполнять можно только назначенную задачу."
            )

        if task.assigned_agent_id != agent.agent_id:
            raise ValueError(
                "Переданный агент не назначен на эту задачу."
            )

        if not agent.enabled:
            raise ValueError(
                "Нельзя выполнять задачу отключённым агентом."
            )

        task.start()

        try:
            result = handler(task, agent)

            if not isinstance(result, str) or not result.strip():
                raise ValueError(
                    "Агент должен вернуть непустой текстовый результат."
                )

            task.complete(result)
        except Exception as exc:
            task.fail(
                f"{type(exc).__name__}: {exc}"
            )

        return task