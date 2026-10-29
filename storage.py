import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "chat_history.db"


def init_db() -> None:
    """Создать базу данных и таблицу истории, если их ещё нет."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session_id
            ON messages (session_id, id)
        """)


def save_message(session_id: str, role: str, content: str) -> None:
    """Сохранить одно сообщение в базу данных."""
    if role not in {"user", "assistant"}:
        raise ValueError("Допустимые роли: user и assistant")

    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            INSERT INTO messages (session_id, role, content)
            VALUES (?, ?, ?)
            """,
            (session_id, role, content),
        )


def load_messages(session_id: str) -> list[dict[str, str]]:
    """Загрузить историю одного диалога по порядку."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT role, content
            FROM messages
            WHERE session_id = ?
            ORDER BY id
            """,
            (session_id,),
        ).fetchall()

    return [
        {"role": row["role"], "content": row["content"]}
        for row in rows
    ]


def list_sessions() -> list[dict]:
    """Получить список сохранённых диалогов."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("""
            SELECT
                session_id,
                MIN(created_at) AS started_at,
                MAX(created_at) AS last_activity,
                COUNT(*) AS message_count,
                (
                    SELECT content
                    FROM messages AS first_message
                    WHERE first_message.session_id = messages.session_id
                      AND first_message.role = 'user'
                    ORDER BY first_message.id
                    LIMIT 1
                ) AS preview
            FROM messages
            GROUP BY session_id
            ORDER BY MAX(id) DESC
        """).fetchall()

    return [
        {
            "session_id": row["session_id"],
            "started_at": row["started_at"],
            "last_activity": row["last_activity"],
            "message_count": row["message_count"],
            "preview": row["preview"] or "(нет сообщений пользователя)",
        }
        for row in rows
    ]