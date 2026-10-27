import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import database


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.docs = root / "documents"
        self.docs.mkdir()
        self.db = root / "test.db"
        self.patches = [patch.object(database, "DB_PATH", self.db),
                        patch.object(database, "DOCUMENTS_PATH", self.docs)]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.addCleanup(self.directory.cleanup)
        self.write("tarjetas.md", "# Tarjetas\n\n## Bloqueo\nBloqueá una tarjeta perdida en el portal.\n\n## Adicionales\nLas adicionales comparten el límite.")

    def write(self, name, content):
        (self.docs / name).write_text(content, encoding="utf-8")

    def test_retrieval_returns_accent_insensitive_sections_with_metadata(self):
        result = database.reindex_documents()
        self.assertEqual(result, {"documents": 1, "chunks": 2})
        sources = database.search("¿Cómo bloqueo una tarjeta perdida?")
        self.assertEqual(sources[0]["section"], "Tarjetas / Bloqueo")
        self.assertEqual(sources[0]["document"], "tarjetas.md")
        self.assertIn("Bloqueá", sources[0]["content"])
        self.assertEqual(database.search("limite")[0]["section"], "Tarjetas / Adicionales")

    def test_reindex_replaces_changed_and_removed_files_without_duplicates(self):
        database.reindex_documents()
        (self.docs / "tarjetas.md").unlink()
        self.write("pagos.md", "# Pagos\n\n## Comprobantes\nGuardá el comprobante.")
        for _ in range(2):
            self.assertEqual(database.reindex_documents(), {"documents": 1, "chunks": 1})
        self.assertEqual(database.search("tarjeta"), [])
        self.assertEqual(database.search("comprobante")[0]["document"], "pagos.md")

    def test_missing_or_unreadable_corpus_preserves_previous_index(self):
        database.reindex_documents()
        (self.docs / "tarjetas.md").unlink()
        with self.assertRaises(ValueError):
            database.reindex_documents()
        self.assertTrue(database.search("tarjeta"))
        (self.docs / "invalido.md").write_bytes(b"\xff")
        with self.assertRaises(UnicodeDecodeError):
            database.reindex_documents()
        self.assertTrue(database.search("tarjeta"))

    def test_query_syntax_is_data_and_empty_or_unrelated_questions_return_nothing(self):
        database.reindex_documents()
        for question in ("", "¿Cómo y de la?", "astronomia galactica", '" OR * - NEAR(', "'); DROP TABLE chunks; --"):
            with self.subTest(question=question):
                self.assertEqual(database.search(question), [])
        self.assertTrue(database.search('"tarjeta" OR *'))
        with closing(sqlite3.connect(self.db)) as connection:
            self.assertEqual(connection.execute("SELECT count(*) FROM chunks").fetchone()[0], 2)

    def test_real_documentation_has_relevant_sources_for_examples(self):
        with patch.object(database, "DOCUMENTS_PATH", Path(__file__).resolve().parent.parent / "documents"):
            database.reindex_documents()
        for question, filename in [
            ("¿Cómo bloqueo una tarjeta perdida?", "seguridad.md"),
            ("¿Dónde consulto el resumen?", "resumen.md"),
            ("¿Cómo reconozco un mensaje falso?", "seguridad.md"),
        ]:
            with self.subTest(question=question):
                self.assertIn(filename, [source["document"] for source in database.search(question)])


class ChunkTests(unittest.TestCase):
    def test_nested_sections_and_long_unbroken_text_are_bounded(self):
        text = "# Manual\n## Pagos\n### Comprobante\n" + "x" * 3000 + "\n## Cuenta\nOtro texto."
        chunks = database.split_markdown(text, "fallback")
        self.assertTrue(all(len(content) <= database.CHUNK_SIZE for _, _, content in chunks))
        self.assertEqual(chunks[0][:2], ("Manual", "Manual / Pagos / Comprobante"))
        self.assertEqual(chunks[-1][1], "Manual / Cuenta")
        self.assertEqual("".join(content for _, _, content in chunks[:-1]), "x" * 3000)


if __name__ == "__main__":
    unittest.main()
