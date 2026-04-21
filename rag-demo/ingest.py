"""
ingest.py - 문서 인덱싱 모듈

이 모듈은 RAG의 첫 번째 단계를 담당합니다:
1. /docs 폴더에서 문서를 읽습니다.
2. 문서를 chunk로 분할합니다.
3. 각 chunk를 OpenAI Embeddings로 임베딩합니다.
4. ChromaDB에 저장합니다.
"""

import os
from typing import List

import chromadb
from openai import OpenAI

from utils import load_documents, prepare_chunks_with_metadata

# 이 파일이 위치한 디렉토리 (경로를 안전하게 잡기 위해 사용)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ChromaDB 저장 경로 (프로젝트 폴더 안에 생성됨)
CHROMA_DIR = os.path.join(BASE_DIR, "chroma_db")
COLLECTION_NAME = "docs_collection"

# 임베딩 모델
EMBEDDING_MODEL = "text-embedding-3-small"


def get_openai_client() -> OpenAI:
    """OpenAI 클라이언트를 생성합니다."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY가 설정되지 않았습니다. "
            ".env 파일에 API 키를 설정해주세요."
        )
    return OpenAI(api_key=api_key)


def get_embeddings(client: OpenAI, texts: List[str]) -> List[List[float]]:
    """
    텍스트 목록을 OpenAI Embeddings API로 임베딩합니다.

    여러 텍스트를 한 번의 API 호출로 한꺼번에 처리합니다.
    (하나씩 보내는 것보다 빠르고 효율적입니다.)
    """
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


def get_chroma_client() -> chromadb.PersistentClient:
    """ChromaDB 클라이언트를 생성합니다."""
    return chromadb.PersistentClient(path=CHROMA_DIR)


def ingest_documents(docs_dir: str = None) -> dict:
    """
    문서를 읽어서 임베딩한 후 ChromaDB에 저장합니다.

    Returns:
        {"doc_count": 문서 수, "chunk_count": 총 chunk 수}
    """
    # docs_dir이 지정되지 않으면 이 파일 기준 ./docs 폴더를 사용
    if docs_dir is None:
        docs_dir = os.path.join(BASE_DIR, "docs")

    # 1단계: 문서 로드
    documents = load_documents(docs_dir)

    if not documents:
        raise ValueError(
            f"'{docs_dir}' 폴더에 .md 또는 .txt 파일이 없습니다. "
            "문서를 추가한 후 다시 시도해주세요."
        )

    # 2단계: chunk 분할 + 메타데이터 부여
    chunks = prepare_chunks_with_metadata(documents)

    if not chunks:
        raise ValueError("문서에서 유효한 텍스트를 추출할 수 없습니다.")

    # 3단계: OpenAI로 임베딩 생성
    client = get_openai_client()
    texts = [chunk["text"] for chunk in chunks]
    embeddings = get_embeddings(client, texts)

    # 4단계: ChromaDB에 저장
    chroma_client = get_chroma_client()

    # 기존 컬렉션이 있으면 삭제 후 새로 생성 (Reindex 지원)
    try:
        chroma_client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "RAG 데모용 문서 컬렉션"},
    )

    # ChromaDB에 데이터 추가
    collection.add(
        ids=[chunk["id"] for chunk in chunks],
        documents=texts,
        embeddings=embeddings,
        metadatas=[chunk["metadata"] for chunk in chunks],
    )

    return {
        "doc_count": len(documents),
        "chunk_count": len(chunks),
    }


def get_collection_info() -> dict:
    """
    현재 ChromaDB 컬렉션의 상태 정보를 반환합니다.

    Returns:
        {"exists": True/False, "chunk_count": chunk 수, "doc_count": 문서 수}
    """
    try:
        chroma_client = get_chroma_client()
        collection = chroma_client.get_collection(COLLECTION_NAME)
        count = collection.count()

        # 저장된 메타데이터에서 고유 문서 파일 수 계산
        if count > 0:
            all_data = collection.get(include=["metadatas"])
            source_files = set(
                m["source_file"] for m in all_data["metadatas"]
            )
            doc_count = len(source_files)
        else:
            doc_count = 0

        return {
            "exists": True,
            "chunk_count": count,
            "doc_count": doc_count,
        }
    except Exception:
        return {"exists": False, "chunk_count": 0, "doc_count": 0}
