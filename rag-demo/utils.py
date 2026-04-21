"""
utils.py - 문서 로딩 및 텍스트 분할 유틸리티

이 모듈은 /docs 폴더의 문서를 읽어오고,
RAG에 사용할 수 있도록 적절한 크기의 chunk로 분할합니다.
"""

import os
from typing import List, Dict


def load_documents(docs_dir: str = "docs") -> List[Dict[str, str]]:
    """
    docs 폴더에서 .md, .txt 파일을 읽어 리스트로 반환합니다.

    Returns:
        [{"filename": "architecture.md", "content": "파일 내용..."}, ...]
    """
    documents = []
    supported_extensions = (".md", ".txt")

    if not os.path.exists(docs_dir):
        raise FileNotFoundError(f"문서 폴더를 찾을 수 없습니다: {docs_dir}")

    for filename in sorted(os.listdir(docs_dir)):
        if not filename.endswith(supported_extensions):
            continue

        filepath = os.path.join(docs_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if content:
            documents.append({"filename": filename, "content": content})

    return documents


def split_into_chunks(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> List[str]:
    """
    텍스트를 지정된 크기의 chunk로 분할합니다.
    chunk 사이에 약간의 겹침(overlap)을 두어 문맥이 끊기지 않도록 합니다.

    Args:
        text: 분할할 원본 텍스트
        chunk_size: 각 chunk의 최대 글자 수
        chunk_overlap: chunk 간 겹치는 글자 수
    """
    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]

        if chunk.strip():
            chunks.append(chunk.strip())

        # 다음 chunk 시작 위치 = 현재 끝 - 겹침 크기
        start = end - chunk_overlap

    return chunks


def prepare_chunks_with_metadata(
    documents: List[Dict[str, str]],
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> List[Dict]:
    """
    문서 목록을 받아 chunk로 분할하고, 각 chunk에 메타데이터를 부여합니다.

    Returns:
        [
            {
                "text": "chunk 내용",
                "metadata": {"source_file": "architecture.md", "chunk_index": 0},
                "id": "architecture.md_0"
            },
            ...
        ]
    """
    all_chunks = []

    for doc in documents:
        filename = doc["filename"]
        chunks = split_into_chunks(doc["content"], chunk_size, chunk_overlap)

        for i, chunk_text in enumerate(chunks):
            all_chunks.append({
                "text": chunk_text,
                "metadata": {
                    "source_file": filename,
                    "chunk_index": i,
                },
                "id": f"{filename}_{i}",
            })

    return all_chunks
