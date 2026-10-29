import json
import sqlite3
import urllib.request
import urllib.error
import uuid

from storage import init_db, save_message, load_messages, list_sessions
from memory import init_memory, add_memory, list_memories, delete_memory
from router.bootstrap import create_router_adapter
from router.commands import handle_agent_command
from router.ollama_client import OllamaClient


OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen3.5:9b-q4_K_M"

SYSTEM_PROMPT = """
Ты — локальный AI-помощник проекта AI Product Lab.
Отвечай на русском языке, если пользователь не попросил другой язык.
Объясняй технические темы последовательно и понятными шагами.
Основной язык программирования проекта — Python.
Перед изменением файлов и настроек предлагай резервную копию.
По умолчанию используй локальные инструменты.
Не отправляй данные в облачные сервисы без явного согласия пользователя.
В вопросах кибербезопасности ориентируйся на законное и безопасное применение.
Если информации недостаточно, честно сообщай об этом.

Долговременная память содержит факты, которые пользователь разрешил сохранить.
Используй эти факты, когда они помогают отвечать точнее.
Не придумывай факты о пользователе и не считай предположения достоверными.
Не изменяй долговременную память самостоятельно.
"""


def build_system_prompt() -> str:
    """Создать системный контекст с актуальными сохранёнными фактами."""
    memories = list_memories()

    if not memories:
        return SYSTEM_PROMPT

    memory_text = "\n".join(
        f"- [{item['id']}] {item['content']}"
        for item in memories
    )

    return (
        SYSTEM_PROMPT
        + "\n\nДОЛГОВРЕМЕННАЯ ПАМЯТЬ ПОЛЬЗОВАТЕЛЯ:\n"
        + memory_text
        + "\n\nИспользуй эти факты только когда они уместны."
    )


def refresh_system_prompt(conversation: list[dict[str, str]]) -> None:
    """Обновить системный контекст, сохранив историю диалога."""
    system_message = {
        "role": "system",
        "content": build_system_prompt(),
    }

    if conversation and conversation[0].get("role") == "system":
        conversation[0] = system_message
    else:
        conversation.insert(0, system_message)


def ask_local_model(messages: list[dict[str, str]]) -> str:
    payload = {
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "think": False,
        "options": {
            "temperature": 0,
            "num_ctx": 4096,
        },
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))

        return result["message"]["content"]

    except urllib.error.URLError as error:
        raise RuntimeError(
            "Не удалось подключиться к локальной Ollama."
        ) from error
    except (KeyError, json.JSONDecodeError) as error:
        raise RuntimeError(
            "Ollama вернула ответ в неожиданном формате."
        ) from error


def choose_session() -> tuple[str, list[dict[str, str]]]:
    sessions = list_sessions()

    print("\nСохранённые диалоги:")

    if sessions:
        for number, session in enumerate(sessions, start=1):
            preview = session["preview"].replace("\n", " ")[:70]
            last_activity = session["last_activity"]
            message_count = session["message_count"]

            print(f"\n{number}. {preview}")
            print(f"   Последняя активность: {last_activity}")
            print(f"   Сообщений: {message_count}")
    else:
        print("Сохранённых диалогов пока нет.")

    print("\n0. Начать новый диалог")

    while True:
        choice = input("\nВыбери номер диалога: ").strip()

        if choice == "0":
            session_id = str(uuid.uuid4())
            conversation = []
            refresh_system_prompt(conversation)
            return session_id, conversation

        try:
            number = int(choice)
        except ValueError:
            print("Введи номер из списка.")
            continue

        if 1 <= number <= len(sessions):
            session_id = sessions[number - 1]["session_id"]
            history = load_messages(session_id)

            conversation = [
                {"role": "system", "content": build_system_prompt()}
            ]
            conversation.extend(history)

            print("История диалога загружена.")
            return session_id, conversation

        print("Такого номера нет. Попробуй ещё раз.")


def show_memories() -> None:
    """Показать все сохранённые факты."""
    memories = list_memories()

    print("\nДолговременная память:")

    if not memories:
        print("Пока нет сохранённых фактов.\n")
        return

    for item in memories:
        print(f"{item['id']}. {item['content']}")

    print()


def handle_memory_command(
    prompt: str,
    conversation: list[dict[str, str]],
) -> bool:
    """
    Обработать команду памяти.
    После изменения памяти обновить системный контекст.
    Вернуть True, если команда обработана.
    """
    command = prompt.strip()
    lowered = command.casefold()

    if lowered == "память":
        show_memories()
        return True

    if lowered.startswith("запомни:"):
        content = command[len("запомни:"):].strip()

        if not content:
            print(
                "Напиши факт после двоеточия. "
                "Пример: запомни: Я изучаю Python\n"
            )
            return True

        try:
            memory_id = add_memory(content)
            refresh_system_prompt(conversation)
            print(f"Факт сохранён. Номер: {memory_id}\n")
        except (ValueError, sqlite3.Error) as error:
            print(f"Не удалось сохранить факт: {error}\n")

        return True

    if lowered.startswith("забудь:"):
        number_text = command[len("забудь:"):].strip()

        try:
            memory_id = int(number_text)
            if memory_id < 1:
                raise ValueError
        except ValueError:
            print("Укажи положительный номер. Пример: забудь: 2\n")
            return True

        try:
            if delete_memory(memory_id):
                refresh_system_prompt(conversation)
                print(f"Факт № {memory_id} удалён.\n")
            else:
                print(f"Факт № {memory_id} не найден.\n")
        except sqlite3.Error as error:
            print(f"Не удалось удалить факт: {error}\n")

        return True

    return False


def main() -> None:
    init_db()
    init_memory()

    session_id, conversation = choose_session()
    router_adapter = create_router_adapter(
        OllamaClient(model=MODEL)
    )

    print("\nPythonRouter — локальный режим")
    print("Модель:", MODEL)
    print("История сохраняется в локальной базе SQLite.")
    print("Долговременная память включена.")
    print("\nКоманды памяти:")
    print("  память          — показать сохранённые факты")
    print("  запомни: текст  — сохранить факт")
    print("  забудь: номер   — удалить факт")
    print("\nКоманды агентов:")
    print("  агенты          — показать список агентов")
    print("  демо: задача    — проверить демонстрационного агента")
    print("  python: задача  — передать задачу Python-агенту")
    print("  python-check: задача — создать код и передать Security Agent")
    print("  Python-агент отвечает текстом и не выполняет код.")
    print("  Отчёт Security Agent не является гарантией безопасности.")
    print("Для выхода введи exit или выход.\n")

    while True:
        try:
            prompt = input("Ты: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nЗавершение работы.")
            break

        if prompt.casefold() in {"exit", "выход"}:
            print("Завершение работы.")
            break

        if not prompt:
            continue

        try:
            if handle_memory_command(prompt, conversation):
                continue

            save_message(session_id, "user", prompt)
            conversation.append(
                {"role": "user", "content": prompt}
            )

            agent_answer = handle_agent_command(
                prompt,
                router_adapter=router_adapter,
            )

            if agent_answer is not None:
                answer = agent_answer
            else:
                answer = ask_local_model(conversation)

            save_message(session_id, "assistant", answer)
            conversation.append(
                {"role": "assistant", "content": answer}
            )

            print(f"\nМодель: {answer}\n")

        except (RuntimeError, sqlite3.Error) as error:
            print(f"\nОшибка: {error}\n")


if __name__ == "__main__":
    main()