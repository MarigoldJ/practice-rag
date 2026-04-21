"""
rag.py - RAG 질의응답 모듈

이 모듈은 RAG의 두 번째 단계를 담당합니다:
1. 사용자 질문을 임베딩합니다.
2. ChromaDB에서 유사한 chunk를 검색합니다.
3. 검색된 chunk를 근거로 OpenAI Responses API를 사용해 답변을 생성합니다.
"""

import os
from typing import List, Dict

from openai import OpenAI

from ingest import (
    get_chroma_client,
    get_openai_client,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
)


def search_similar_chunks(
    query: str,
    top_k: int = 3,
) -> List[Dict]:
    """
    사용자 질문과 유사한 chunk를 ChromaDB에서 검색합니다.

    Args:
        query: 사용자 질문
        top_k: 반환할 결과 수

    Returns:
        [
            {
                "text": "chunk 내용",
                "source_file": "architecture.md",
                "chunk_index": 0,
                "distance": 0.23
            },
            ...
        ]
    """
    # 질문을 임베딩
    client = get_openai_client()
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=query,
    )
    query_embedding = response.data[0].embedding

    # ChromaDB에서 유사도 검색
    chroma_client = get_chroma_client()
    collection = chroma_client.get_collection(COLLECTION_NAME)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    # 결과를 보기 좋은 형태로 변환
    search_results = []
    for i in range(len(results["ids"][0])):
        search_results.append({
            "text": results["documents"][0][i],
            "source_file": results["metadatas"][0][i]["source_file"],
            "chunk_index": results["metadatas"][0][i]["chunk_index"],
            "distance": results["distances"][0][i],
        })

    return search_results


def generate_answer(query: str, context_chunks: List[Dict]) -> str:
    """
    검색된 chunk를 근거로 OpenAI Responses API를 사용해 답변을 생성합니다.

    핵심: 검색된 문서 내용만을 근거로 답변하며,
    근거가 부족하면 솔직하게 "근거를 찾지 못했다"고 답합니다.
    """
    # 검색된 chunk들을 하나의 컨텍스트 문자열로 조합
    context_parts = []
    for i, chunk in enumerate(context_chunks):
        context_parts.append(
            f"[근거 {i + 1}] (출처: {chunk['source_file']}, "
            f"chunk #{chunk['chunk_index']})\n{chunk['text']}"
        )

    context_text = "\n\n---\n\n".join(context_parts)

    # 시스템 프롬프트: RAG의 핵심 - 근거 기반 답변만 하도록 지시
    system_prompt = """당신은 프로젝트 운영 문서를 기반으로 질문에 답변하는 어시스턴트입니다.

반드시 아래 규칙을 따르세요:
1. 제공된 "검색된 문서 근거"에 있는 내용만을 바탕으로 답변하세요.
2. 근거에 없는 내용을 추측하거나 지어내지 마세요.
3. 근거가 불충분하면 "문서에서 충분한 근거를 찾지 못했습니다. 질문을 더 구체적으로 해주시거나, 관련 문서를 추가해주세요."라고 답하세요.
4. 답변 시 어떤 근거를 참고했는지 언급하세요.
5. 답변은 한국어로 작성하세요."""

    user_message = f"""## 검색된 문서 근거

{context_text}

## 사용자 질문

{query}

위 문서 근거만을 바탕으로 질문에 답변해주세요."""

    # OpenAI Responses API 호출
    client = get_openai_client()
    response = client.responses.create(
        model="gpt-4.1-nano",
        instructions=system_prompt,
        input=user_message,
    )

    return response.output_text


def ask(query: str) -> Dict:
    """
    RAG 파이프라인의 전체 흐름을 실행합니다.

    1. 질문 → 임베딩 → ChromaDB 검색
    2. 검색 결과 → OpenAI → 답변 생성

    Returns:
        {
            "answer": "생성된 답변",
            "sources": [검색된 chunk 정보 리스트],
        }
    """
    # 1단계: 관련 문서 검색
    sources = search_similar_chunks(query, top_k=3)

    # 2단계: 검색 결과를 근거로 답변 생성
    answer = generate_answer(query, sources)

    return {
        "answer": answer,
        "sources": sources,
    }
