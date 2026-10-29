
"""Последовательная разработка и проверка безопасности Python-кода."""

from dataclasses import dataclass

from router.adapter import AdapterResult, RouterAdapter
from router.task import TaskStatus


@dataclass(frozen=True)
class WorkflowResult:
    """Результат последовательной работы двух агентов."""

    success: bool
    message: str
    requirements: str
    code: str | None
    security_report: str | None
    python_step: AdapterResult | None
    security_step: AdapterResult | None


class PythonSecurityWorkflow:
    """Последовательно запускает Python Agent и Security Agent."""

    def __init__(self, adapter: RouterAdapter) -> None:
        self.adapter = adapter

    def run(self, requirements: str) -> WorkflowResult:
        """Создать код и передать его на проверку безопасности."""

        if not isinstance(requirements, str) or not requirements.strip():
            return WorkflowResult(
                success=False,
                message="Требования не могут быть пустыми.",
                requirements=(
                    requirements if isinstance(requirements, str) else ""
                ),
                code=None,
                security_report=None,
                python_step=None,
                security_step=None,
            )

        python_step = self.adapter.execute(
            description=requirements,
            required_capabilities=("python",),
        )

        if (
            not python_step.success
            or python_step.status != TaskStatus.COMPLETED
            or not isinstance(python_step.result, str)
            or not python_step.result.strip()
        ):
            return WorkflowResult(
                success=False,
                message=(
                    "Этап Python Agent завершился неуспешно: "
                    + python_step.message
                ),
                requirements=requirements,
                code=None,
                security_report=None,
                python_step=python_step,
                security_step=None,
            )

        code = python_step.result

        security_description = (
            "ИСХОДНЫЕ ТРЕБОВАНИЯ:\n"
            + requirements
            + "\n\n"
            + "КОД И ОТВЕТ PYTHON AGENT ДЛЯ ПРОВЕРКИ:\n"
            + code
        )

        security_step = self.adapter.execute(
            description=security_description,
            required_capabilities=("security",),
        )

        if (
            not security_step.success
            or security_step.status != TaskStatus.COMPLETED
            or not isinstance(security_step.result, str)
            or not security_step.result.strip()
        ):
            return WorkflowResult(
                success=False,
                message=(
                    "Этап Security Agent завершился неуспешно: "
                    + security_step.message
                ),
                requirements=requirements,
                code=code,
                security_report=None,
                python_step=python_step,
                security_step=security_step,
            )

        return WorkflowResult(
            success=True,
            message="Создание кода и проверка безопасности завершены.",
            requirements=requirements,
            code=code,
            security_report=security_step.result,
            python_step=python_step,
            security_step=security_step,
        )
