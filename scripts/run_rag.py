#!/usr/bin/env python3
"""
Query the RAG index:
- embed query
- retrieve top-k chunks from Qdrant
- print sources + (optional) generate answer
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from src.utils.rag_config_loader import load_rag_config
from src.rag import retrieve_context
from src.rag.generate import generate_with_gemini


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="Query Old Mutual RAG index")
    parser.add_argument("question", type=str, help="User question")
    parser.add_argument("--config", type=Path, default=None, help="Path to rag_config.yml")
    parser.add_argument("--top-k", type=int, default=None, help="Override top_k from config")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    # Load .env safely (no need to source in shell)
    load_dotenv()

    setup_logging(args.verbose)
    cfg = load_rag_config(args.config)
    top_k = args.top_k or cfg.retrieval.top_k
    hits = retrieve_context(args.question, cfg, top_k=top_k)

    print("\n### Retrieved context\n")
    for i, h in enumerate(hits, start=1):
        p = h["payload"]
        print(f"[{i}] score={h['score']:.4f} chunk_id={h['id']}")
        print(f"    type={p.get('type')} chunk_type={p.get('chunk_type')} title={p.get('title')}")
        print(f"    url={p.get('url')}")
        if p.get("section_heading"):
            print(f"    heading={p.get('section_heading')}")
        text = (p.get("text") or "").strip()
        preview = text[:350].replace("\n", "\\n")
        print(f"    text={preview}")
        print()

    if cfg.generation.enabled:
        try:
            if cfg.generation.backend == "gemini":
                answer = generate_with_gemini(
                    question=args.question,
                    hits=hits,
                    model=cfg.generation.model,
                    api_key_env=cfg.generation.api_key_env,
                )
            else:
                # Minimal OpenAI answerer (optional)
                from openai import OpenAI

                client = OpenAI()
                context = "\n\n".join([h["payload"].get("text", "") for h in hits])
                prompt = (
                    "You are a helpful assistant. Answer the question using ONLY the context.\n"
                    "If the context is insufficient, say what is missing.\n\n"
                    f"Question: {args.question}\n\n"
                    f"Context:\n{context}\n"
                )
                resp = client.chat.completions.create(
                    model=cfg.generation.model,
                    messages=[{"role": "user", "content": prompt}],
                )
                answer = resp.choices[0].message.content

            print("\n### Answer\n")
            print(answer)
        except Exception as e:
            print("\n### Answer\n")
            print(f"[Generation failed: {type(e).__name__}: {e}]")
            print("Retrieved context above is correct; fix generator quota/keys or disable generation in config.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

