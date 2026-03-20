from pathlib import Path

from src.database.postgres import PostgresDB
from src.database.security import hash_phone_number, normalize_phone_number
from src.processors.knowledge_base import KnowledgeBaseProcessor
from src.utils.processing_config_loader import ProcessingConfig


def test_phone_hash_lookup_normalizes_number():
    db = PostgresDB()
    user = db.get_or_create_user("+256 700 000 001")

    same = db.get_user_by_phone("256700000001")

    assert same is not None
    assert same.id == user.id
    assert user.phone_hash == hash_phone_number(normalize_phone_number("+256 700 000 001"))


def test_kb_processor_builds_chunks_from_text_file(tmp_path: Path):
    source = tmp_path / "sample.txt"
    source.write_text("Motor private insurance protects private vehicles against accident and theft. " * 20, encoding="utf-8")

    processor = KnowledgeBaseProcessor(ProcessingConfig())
    chunks_path = processor.build_chunks_file(source, tmp_path / "processed")

    assert chunks_path.exists()
    rows = chunks_path.read_text(encoding="utf-8").strip().splitlines()
    assert rows
    assert '"type": "kb_upload"' in rows[0]
