import sqlite3
from contextlib import closing
from pathlib import Path


DEFAULT_DB_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "chat_history.db"
)


def init_memory(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Создать таблицу долговременной памяти, если её ещё нет."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)


def add_memory(content: str, db_path: Path = DEFAULT_DB_PATH) -> int:
    """Сохранить подтверждённый факт и вернуть его номер."""
    content = content.strip()

    if not content:
        raise ValueError("Нельзя сохранить пустой факт.")

    init_memory(db_path)

    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            cursor = connection.execute(
                "INSERT INTO memories (content) VALUES (?)",
                (content,),
            )
            return int(cursor.lastrowid)


def list_memories(db_path: Path = DEFAULT_DB_PATH) -> list[dict]:
    """Получить сохранённые факты по порядку."""
    init_memory(db_path)

    with closing(sqlite3.connect(db_path)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("""
            SELECT id, content, created_at
            FROM memories
            ORDER BY id
        """).fetchall()

    return [dict(row) for row in rows]


def delete_memory(memory_id: int, db_path: Path = DEFAULT_DB_PATH) -> bool:
    """Удалить факт по номеру; вернуть True, если он существовал."""
    init_memory(db_path)

    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            cursor = connection.execute(
                "DELETE FROM memories WHERE id = ?",
                (memory_id,),
            )
            return cursor.rowcount > 0
