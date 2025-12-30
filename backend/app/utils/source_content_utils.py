"""
Source Content Utilities - Shared functions for loading source content.

Used by multiple agents (blog, website, etc.) to get source content
with smart sampling for large sources.
"""

import os
from typing import Optional

from app.utils.path_utils import get_sources_dir


def get_source_content(
    project_id: str,
    source_id: str,
    max_chars: int = 15000,
    max_chunks: int = 12
) -> str:
    """
    Get source content for AI processing.

    For small sources: returns full content.
    For large sources: samples chunks evenly distributed.

    Args:
        project_id: Project ID
        source_id: Source ID
        max_chars: Max characters before sampling (default 15000 ~3500 tokens)
        max_chunks: Max chunks to sample for large sources

    Returns:
        Source content string
    """
    try:
        from app.services.source_services import source_service

        source = source_service.get_source(project_id, source_id)
        if not source:
            return "Error: Source not found"

        sources_dir = get_sources_dir(project_id)
        processed_path = os.path.join(sources_dir, "processed", f"{source_id}.txt")

        if not os.path.exists(processed_path):
            return f"Source: {source.get('name', 'Unknown')}\n(Content not yet processed)"

        with open(processed_path, "r", encoding="utf-8") as f:
            full_content = f.read()

        # Small source: return all
        if len(full_content) < max_chars:
            return full_content

        # Large source: try to sample chunks
        chunks_dir = os.path.join(sources_dir, "chunks", source_id)
        if not os.path.exists(chunks_dir):
            return full_content[:max_chars] + "\n\n[Content truncated...]"

        chunk_files = sorted([
            f for f in os.listdir(chunks_dir)
            if f.endswith(".txt") and f.startswith(source_id)
        ])

        if not chunk_files:
            return full_content[:max_chars] + "\n\n[Content truncated...]"

        # Sample chunks evenly distributed
        if len(chunk_files) <= max_chunks:
            selected_chunks = chunk_files
        else:
            step = len(chunk_files) / max_chunks
            selected_chunks = [chunk_files[int(i * step)] for i in range(max_chunks)]

        sampled_content = []
        for chunk_file in selected_chunks:
            chunk_path = os.path.join(chunks_dir, chunk_file)
            with open(chunk_path, "r", encoding="utf-8") as f:
                sampled_content.append(f.read())

        return "\n\n".join(sampled_content)

    except Exception as e:
        return f"Error loading source content: {str(e)}"


def get_source_name(project_id: str, source_id: str) -> Optional[str]:
    """Get source name by ID."""
    try:
        from app.services.source_services import source_service
        source = source_service.get_source(project_id, source_id)
        return source.get("name") if source else None
    except Exception:
        return None
