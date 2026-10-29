"""Демонстрация Python -> Security без истории чата и исполнения кода."""

from time import perf_counter

from router.adapter import AdapterResult
from router.bootstrap import create_router_adapter
from router.ollama_client import OllamaClient
from router.python_agent import ChatClient
from router.workflow import PythonSecurityWorkflow


MODEL = "qwen3.5:9b-q4_K_M"
TIMEOUT_SECONDS = 300
REQUIREMENTS = (
    "Напиши функцию sum_positive(numbers): принимает список целых чисел, "
    "возвращает сумму положительных, для пустого списка — 0. "
    "Не изменяет исходный список. Если аргумент не список, "
    "элемент не int или является bool — вызывает TypeError. "
    "Без файлов, сети, внешних библиотек, eval и exec. "
    "Ответь кратко: функция в одном блоке кода и два предложения пояснения."
)


class TracedClient:
    """Показать начало и длительность каждого вызова переданного клиента."""

    def __init__(self, client: ChatClient) -> None:
        self.client = client
        self.calls = 0

    def chat(self, prompt: str) -> str:
        self.calls += 1
        number = self.calls
        started = perf_counter()
        print(f"\n[Запрос {number}] Начало", flush=True)

        try:
            answer = self.client.chat(prompt)
        except Exception as error:
            elapsed = perf_counter() - started
            print(
                f"[Запрос {number}] Ошибка через {elapsed:.1f} с: {error}",
                flush=True,
            )
            raise

        elapsed = perf_counter() - started
        print(f"[Запрос {number}] Ответ получен за {elapsed:.1f} с", flush=True)
        return answer


def print_step(label: str, step: AdapterResult | None) -> None:
    """Показать статус этапа или отметить, что он не запускался."""
    print(f"\n=== {label} ===")
    if step is None:
        print("Этап не запускался.")
        return

    print("Агент:", step.agent_id)
    print("Успех:", step.success)
    print("Статус:", step.status.value if step.status is not None else "не указан")
    print("Сообщение:", step.message)


def run_demo(client: ChatClient) -> int:
    """Запустить workflow; вернуть 0 при техническом успехе, иначе 1."""
    traced_client = TracedClient(client)
    workflow = PythonSecurityWorkflow(create_router_adapter(traced_client))

    print("Задача:", REQUIREMENTS)
    print("\nЗапуск Python -> Security...", flush=True)
    started = perf_counter()
    result = workflow.run(REQUIREMENTS)
    elapsed = perf_counter() - started

    print("\n=== РЕЗУЛЬТАТ WORKFLOW ===")
    print("Технический успех:", result.success)
    print("Сообщение:", result.message)
    print("Вызовов модели:", traced_client.calls)
    print(f"Общее время: {elapsed:.1f} с")

    print_step("PYTHON AGENT", result.python_step)
    print_step("SECURITY AGENT", result.security_step)

    print("\n=== ОТВЕТ PYTHON AGENT ===")
    print(result.code if result.code is not None else "Ответ не получен.")
    print("\n=== ОТЧЁТ SECURITY AGENT ===")
    print(
        result.security_report
        if result.security_report is not None
        else "Отчёт не получен."
    )

    print(
        "\nУспешное завершение этапов не доказывает безопасность кода. "
        "Сгенерированный код не выполнялся."
    )
    return 0 if result.success else 1


def main() -> int:
    print("PythonRouter — отдельная демонстрация workflow")
    print("Модель:", MODEL)
    print("Тайм-аут каждого запроса:", TIMEOUT_SECONDS, "с")
    client = OllamaClient(model=MODEL, timeout=TIMEOUT_SECONDS)
    return run_demo(client)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nДемонстрация прервана пользователем.")
        raise SystemExit(130)