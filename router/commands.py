"""Обработка явных команд агентов PythonRouter."""

from router.adapter import RouterAdapter
from router.integration import execute_demo_task
from router.ollama_client import OllamaClient
from router.python_agent import ChatClient
from router.python_integration import execute_python_task
from router.workflow import PythonSecurityWorkflow, WorkflowResult


def _format_workflow_result(result: WorkflowResult) -> str:
    """Показать результаты этапов без утверждения о безопасности кода."""
    outcome = "завершено" if result.success else "ошибка"
    sections = [
        "Последовательная работа: Python -> Security",
        f"Технический результат: {outcome}",
        result.message,
    ]

    for label, step in (
        ("Python Agent", result.python_step),
        ("Security Agent", result.security_step),
    ):
        if step is None:
            sections.append(f"{label}: этап не запускался.")
            continue

        status = step.status.value if step.status is not None else "не указан"
        agent_id = step.agent_id if step.agent_id is not None else "не назначен"
        sections.append(
            f"{label}:\n"
            f"Агент: {agent_id}\n"
            f"Статус: {status}\n"
            f"Сообщение: {step.message}"
        )

    if result.code is not None:
        sections.append("Ответ Python Agent:\n" + result.code)
    else:
        sections.append("Ответ Python Agent не получен.")

    if result.security_report is not None:
        sections.append("Отчёт Security Agent:\n" + result.security_report)
    else:
        sections.append("Отчёт Security Agent не получен.")

    sections.append(
        "Важно: успешное завершение этапов не доказывает безопасность кода. "
        "Сгенерированный код не выполнялся."
    )
    return "\n\n".join(sections)


def handle_agent_command(
    prompt: str,
    *,
    python_client: ChatClient | None = None,
    router_adapter: RouterAdapter | None = None,
) -> str | None:
    """
    Обработать команду агента или вернуть None для обычного диалога.

    router_adapter позволяет использовать общий маршрутизатор.
    python_client предназначен для вызовов без общего адаптера.
    Одновременно передавать оба параметра нельзя.
    Команды «агенты» и «python-check:» требуют общего адаптера.
    """
    if python_client is not None and router_adapter is not None:
        raise ValueError(
            "Передайте либо router_adapter, либо python_client."
        )

    if not isinstance(prompt, str):
        return None

    command = prompt.strip()
    lowered = command.casefold()

    if lowered == "агенты":
        if router_adapter is None:
            return (
                "Ошибка: для команды 'агенты' "
                "необходим общий маршрутизатор."
            )

        agents = router_adapter.list_agents()

        if not agents:
            return "В реестре пока нет агентов."

        entries = []
        for agent in agents:
            state = "включён" if agent.enabled else "отключён"
            capabilities = ", ".join(agent.capabilities)
            entries.append(
                f"ID: {agent.agent_id}\n"
                f"Название: {agent.name}\n"
                f"Возможности: {capabilities}\n"
                f"Состояние: {state}"
            )

        return "Зарегистрированные агенты:\n\n" + "\n\n".join(entries)

    if lowered.startswith("python-check:"):
        description = command.split(":", 1)[1].strip()

        if not description:
            return (
                "Ошибка: после команды 'python-check:' "
                "необходимо указать описание задачи."
            )

        if router_adapter is None:
            return (
                "Ошибка: для команды 'python-check:' "
                "необходим общий маршрутизатор."
            )

        workflow = PythonSecurityWorkflow(router_adapter)
        return _format_workflow_result(workflow.run(description))

    if lowered.startswith("демо:"):
        prefix = "демо:"
        capability = "demo"
    elif lowered.startswith("python:"):
        prefix = "python:"
        capability = "python"
    else:
        return None

    description = command.split(":", 1)[1].strip()

    if not description:
        return (
            f"Ошибка: после команды '{prefix}' "
            "необходимо указать описание задачи."
        )

    if router_adapter is not None:
        result = router_adapter.execute(
            description=description,
            required_capabilities=(capability,),
        )
    elif capability == "demo":
        result = execute_demo_task(description)
    else:
        client = (
            python_client
            if python_client is not None
            else OllamaClient()
        )
        result = execute_python_task(description, client)

    if not result.success:
        return f"Ошибка выполнения: {result.message}"

    return (
        f"Агент: {result.agent_id}\n"
        f"Статус: {result.status.value}\n"
        f"Результат: {result.result}"
    )