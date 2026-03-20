from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request

from src.processors.knowledge_base import KnowledgeBaseProcessor
from src.rag.ingest import ingest_chunks_to_qdrant
from src.utils.processing_config_loader import load_processing_config
from src.utils.rag_config_loader import load_rag_config

logger = logging.getLogger(__name__)

router = APIRouter()


def _run_ingest(saved_path: Path) -> None:
    processing_cfg = load_processing_config()
    kb_processor = KnowledgeBaseProcessor(processing_cfg)
    processed_dir = saved_path.parent / "processed"
    chunks_path = kb_processor.build_chunks_file(saved_path, processed_dir)
    rag_cfg = load_rag_config()
    ingest_chunks_to_qdrant(chunks_path, rag_cfg)


@router.post("/admin/knowledge-base/upload", tags=["Admin"])
async def upload_knowledge_base_file(
    request: Request,
    background_tasks: BackgroundTasks,
    filename: str = Query(..., min_length=1),
    trigger_ingest: bool = True,
):
    safe_name = Path(filename).name
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    upload_root = Path("data") / "uploads" / "knowledge_base"
    upload_root.mkdir(parents=True, exist_ok=True)
    saved_path = upload_root / f"{timestamp}_{safe_name}"

    body = await request.body()
    if not body:
        raise HTTPException(status_code=400, detail="Empty upload body")
    with saved_path.open("wb") as buffer:
        buffer.write(body)

    ingest_status = "stored_only"
    if trigger_ingest and saved_path.suffix.lower() in {".jsonl", ".pdf", ".txt", ".md"}:
        background_tasks.add_task(_run_ingest, saved_path)
        ingest_status = "scheduled"
    elif trigger_ingest:
        ingest_status = "unsupported_for_auto_ingest"

    return {
        "filename": safe_name,
        "saved_path": str(saved_path),
        "ingest_status": ingest_status,
    }
