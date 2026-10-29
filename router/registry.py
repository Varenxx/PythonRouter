"""Реестр специализированных агентов PythonRouter."""

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Agent:
    """Описание одного специализированного агента."""

    agent_id: str
    name: str
    role: str
    capabilities: tuple[str, ...]
    enabled: bool = True


class AgentRegistry:
    """Хранит и предоставляет доступ к зарегистрированным агентам."""

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}

    def register(self, agent: Agent) -> None:
        """Регистрирует агента, если его ID ещё не занят."""

        agent_id = agent.agent_id.strip()

        if not agent_id:
            raise ValueError("ID агента не может быть пустым.")

        if agent_id in self._agents:
            raise ValueError(
                f"Агент с ID '{agent_id}' уже зарегистрирован."
            )

        if not agent.name.strip():
            raise ValueError("Имя агента не может быть пустым.")

        if not agent.role.strip():
            raise ValueError("Роль агента не может быть пустой.")

        normalized_capabilities = tuple(
            capability.strip().casefold()
            for capability in agent.capabilities
            if capability.strip()
        )

        if not normalized_capabilities:
            raise ValueError(
                "У агента должна быть хотя бы одна возможность."
            )

        normalized_agent = Agent(
            agent_id=agent_id,
            name=agent.name.strip(),
            role=agent.role.strip(),
            capabilities=normalized_capabilities,
            enabled=agent.enabled,
        )

        self._agents[agent_id] = normalized_agent

    def get(self, agent_id: str) -> Agent | None:
        """Возвращает агента по ID или None, если он не найден."""

        return self._agents.get(agent_id.strip())

    def list_agents(self) -> list[Agent]:
        """Возвращает список всех зарегистрированных агентов."""

        return list(self._agents.values())

    def find_by_capability(
        self,
        capability: str,
    ) -> list[Agent]:
        """Находит включённых агентов с указанной возможностью."""

        normalized_capability = capability.strip().casefold()

        if not normalized_capability:
            return []

        return [
            agent
            for agent in self._agents.values()
            if agent.enabled
            and normalized_capability in agent.capabilities
        ]

    def enable(self, agent_id: str) -> bool:
        """Включает агента. Возвращает False, если он не найден."""

        agent = self.get(agent_id)

        if agent is None:
            return False

        self._agents[agent.agent_id] = Agent(
            agent_id=agent.agent_id,
            name=agent.name,
            role=agent.role,
            capabilities=agent.capabilities,
            enabled=True,
        )
        return True

    def disable(self, agent_id: str) -> bool:
        """Отключает агента без удаления его записи."""

        agent = self.get(agent_id)

        if agent is None:
            return False

        self._agents[agent.agent_id] = Agent(
            agent_id=agent.agent_id,
            name=agent.name,
            role=agent.role,
            capabilities=agent.capabilities,
            enabled=False,
        )
        return True

    def remove(self, agent_id: str) -> bool:
        """Удаляет агента. Возвращает False, если он не найден."""

        normalized_id = agent_id.strip()

        if normalized_id not in self._agents:
            return False

        del self._agents[normalized_id]
        return True