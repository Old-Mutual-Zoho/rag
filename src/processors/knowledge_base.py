from __future__ import annotations

import json
from pathlib import Path
from typing import List
from uuid import uuid4

from PyPDF2 import PdfReader

from src.processors.oldmutual_cleaner import OldMutualCleaner
from src.utils.processing_config_loader import ProcessingConfig


def _split_words(text: str, chunk_size_words: int, overlap_words: int) -> List[str]:
    words = text.split()
    if not words:
        return []
    if len(words) <= chunk_size_words:
        return [" ".join(words)]

    overlap_words = max(0, min(overlap_words, chunk_size_words - 1))
    step = max(1, chunk_size_words - overlap_words)
    chunks: List[str] = []
    for start in range(0, len(words), step):
        end = min(len(words), start + chunk_size_words)
        part = " ".join(words[start:end]).strip()
        if part:
            chunks.append(part)
        if end >= len(words):
            break
    return chunks


class KnowledgeBaseProcessor:
    def __init__(self, config: ProcessingConfig) -> None:
        self.config = config
        self.cleaner = OldMutualCleaner(
            normalize_unicode=config.cleaning.normalize_unicode,
            fix_ocr_errors=config.cleaning.fix_ocr_errors,
            normalize_terminology=config.cleaning.normalize_terminology,
            improve_step_headings=False,
        )

    def extract_text(self, path: Path) -> str:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            reader = PdfReader(str(path))
            pages = [(page.extract_text() or "").strip() for page in reader.pages]
            return "\n\n".join(page for page in pages if page)
        return path.read_text(encoding="utf-8", errors="replace")

    def build_chunks_file(self, source_path: Path, output_dir: Path) -> Path:
        output_dir.mkdir(parents=True, exist_ok=True)
        if source_path.suffix.lower() == ".jsonl":
            return source_path

        raw_text = self.cleaner.clean_text(self.extract_text(source_path))
        chunk_size = max(100, int(self.config.chunking.chunk_size))
        overlap = min(int(self.config.chunking.chunk_overlap), max(0, chunk_size - 1))
        chunk_words = max(50, chunk_size // 6)
        overlap_words = min(chunk_words - 1, max(0, overlap // 6))
        chunks = _split_words(raw_text, chunk_words, overlap_words)

        chunks_path = output_dir / f"{source_path.stem}_chunks.jsonl"
        with chunks_path.open("w", encoding="utf-8") as f:
            for idx, chunk in enumerate(chunks):
                row = {
                    "id": f"upload:{source_path.stem}:{uuid4().hex[:12]}:{idx}",
                    "doc_id": f"upload:{source_path.stem}",
                    "text": chunk,
                    "title": source_path.stem.replace("_", " ").title(),
                    "source_path": str(source_path),
                    "type": "kb_upload",
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

        return chunks_path
