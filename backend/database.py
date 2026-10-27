import re
import sqlite3
import unicodedata
from contextlib import closing
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "finassist.db"
DOCUMENTS_PATH = Path(__file__).resolve().parent.parent / "documents"
CHUNK_SIZE = 1400
STOP_WORDS = set("a al algo como con cual cuales cuando cuanto de del donde el ella en es esta este estos finnova hay la las lo los me mi mis o para por puedo que se si sin sobre su sus tengo un una unos y yo".split())


def init_db() -> None:
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
                document UNINDEXED, title, section, content,
                tokenize='unicode61 remove_diacritics 2'
            )
        """)
        connection.commit()


def split_markdown(text: str, fallback_title: str) -> list[tuple[str, str, str]]:
    """Keep each heading with its body; bound large sections without extra parsers."""
    title = fallback_title
    headings: dict[int, str] = {}
    body: list[str] = []
    chunks = []

    def flush() -> None:
        content = "\n".join(body).strip()
        section = " / ".join(headings.values()) or title
        while content:
            end = len(content)
            if end > CHUNK_SIZE:
                end = content.rfind(" ", 0, CHUNK_SIZE + 1)
                if end < CHUNK_SIZE // 2:
                    end = CHUNK_SIZE
            chunks.append((title, section, content[:end].strip()))
            content = content[end:].strip()
        body.clear()

    for line in text.splitlines():
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if heading:
            flush()
            level = len(heading[1])
            if level == 1:
                title = heading[2]
            headings = {depth: value for depth, value in headings.items() if depth < level}
            headings[level] = heading[2]
        else:
            body.append(line)
    flush()
    return chunks


def reindex_documents() -> dict[str, int]:
    paths = sorted(DOCUMENTS_PATH.rglob("*.md"))
    if not paths:
        raise ValueError("No se encontraron documentos Markdown en documents/.")
    rows = []
    for path in paths:
        document = path.relative_to(DOCUMENTS_PATH).as_posix()
        for title, section, content in split_markdown(path.read_text(encoding="utf-8"), path.stem):
            rows.append((document, title, section, content))
    if not rows:
        raise ValueError("Los documentos Markdown no contienen texto para indexar.")
    init_db()
    # Replace the complete index in one transaction, including removed documents.
    with closing(sqlite3.connect(DB_PATH)) as connection, connection:
        connection.execute("DELETE FROM chunks")
        connection.executemany(
            "INSERT INTO chunks (document, title, section, content) VALUES (?, ?, ?, ?)", rows
        )
    return {"documents": len(paths), "chunks": len(rows)}


def search(question: str, limit: int = 5) -> list[dict]:
    normalized = "".join(
        char for char in unicodedata.normalize("NFD", question.lower())
        if unicodedata.category(char) != "Mn"
    )
    tokens = list(dict.fromkeys(
        token for token in re.findall(r"[^\W_]+", normalized)
        if len(token) > 1 and token not in STOP_WORDS
    ))[:40]
    if not tokens:
        return []
    # Build FTS syntax from tokens only; user operators and quotes never reach MATCH.
    query = " OR ".join(f'"{token}"' + ("*" if len(token) >= 4 else "") for token in tokens)
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """SELECT rowid AS id, document, title, section, content
               FROM chunks WHERE chunks MATCH ?
               ORDER BY bm25(chunks, 0, 2, 3, 1), rowid LIMIT ?""",
            (query, limit),
        ).fetchall()
    return [dict(row) for row in rows]


if __name__ == "__main__":
    result = reindex_documents()
    print(f"Índice actualizado: {result['documents']} documentos, {result['chunks']} fragmentos.")
