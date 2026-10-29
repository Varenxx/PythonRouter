"""Публичный интерфейс пакета маршрутизации задач PythonRouter."""

from router.registry import Agent, AgentRegistry
from router.task import Task, TaskStatus
from router.dispatcher import RoutingResult, TaskDispatcher
from router.executor import AgentHandler, TaskExecutor
from router.service import RouterService, ServiceResult

__all__ = [
    "Agent",
    "AgentRegistry",
    "Task",
    "TaskStatus",
    "RoutingResult",
    "TaskDispatcher",
    "AgentHandler",
    "TaskExecutor",
    "RouterService",
    "ServiceResult",
]