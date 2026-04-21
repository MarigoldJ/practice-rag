"""
app.py - Streamlit 기반 RAG 데모 웹앱

문서 기반 RAG(Retrieval-Augmented Generation) 데모 애플리케이션입니다.
사용자가 질문하면 관련 문서를 검색하고, 그 근거를 바탕으로 답변합니다.
"""

import streamlit as st
from dotenv import load_dotenv

from ingest import ingest_documents, get_collection_info
from rag import ask

# .env 파일에서 환경 변수 로드
load_dotenv()

# 페이지 기본 설정
st.set_page_config(
    page_title="RAG 데모 - 문서 기반 질의응답",
    page_icon="📚",
    layout="wide",
)

# 샘플 질문 목록
SAMPLE_QUESTIONS = [
    "시스템의 전체 아키텍처는 어떻게 구성되어 있나요?",
    "배포할 때 롤백은 어떻게 하나요?",
    "API 서버 응답이 느려지면 어떻게 대응해야 하나요?",
]


def render_sidebar():
    """사이드바 UI를 렌더링합니다."""
    with st.sidebar:
        st.header("📚 RAG 데모")
        st.markdown(
            "이 앱은 `/docs` 폴더의 문서를 기반으로 "
            "질문에 답변하는 RAG 데모입니다."
        )

        st.divider()

        st.subheader("⚙️ 설정 안내")
        st.markdown(
            "`.env` 파일에 `OPENAI_API_KEY`를 설정해야 합니다.\n\n"
            "```\nOPENAI_API_KEY=sk-...\n```"
        )

        st.divider()

        # Reindex 버튼
        st.subheader("🔄 문서 인덱싱")
        if st.button("📥 Reindex (문서 다시 인덱싱)", use_container_width=True):
            with st.spinner("문서를 인덱싱하는 중..."):
                try:
                    result = ingest_documents()
                    st.success(
                        f"인덱싱 완료! "
                        f"문서 {result['doc_count']}개, "
                        f"chunk {result['chunk_count']}개"
                    )
                except FileNotFoundError as e:
                    st.error(f"❌ {e}")
                except ValueError as e:
                    st.error(f"❌ {e}")
                except Exception as e:
                    st.error(f"❌ 인덱싱 실패: {e}")

        st.divider()

        # 샘플 질문 버튼
        st.subheader("💡 샘플 질문")
        for question in SAMPLE_QUESTIONS:
            if st.button(question, use_container_width=True):
                st.session_state["user_query"] = question


def render_main():
    """메인 화면 UI를 렌더링합니다."""
    st.title("📖 문서 기반 RAG 데모")
    st.markdown(
        "프로젝트 운영 문서를 기반으로 질문하면, "
        "관련 문서를 검색한 뒤 근거를 바탕으로 답변합니다."
    )

    # 현재 인덱싱 상태 표시
    info = get_collection_info()
    if info["exists"]:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("📄 인덱싱된 문서 수", f"{info['doc_count']}개")
        with col2:
            st.metric("🧩 총 chunk 수", f"{info['chunk_count']}개")
    else:
        st.warning(
            "⚠️ 아직 인덱싱된 문서가 없습니다. "
            "사이드바의 'Reindex' 버튼을 눌러 문서를 인덱싱해주세요."
        )

    st.divider()

    # 질문 입력
    default_query = st.session_state.get("user_query", "")
    user_query = st.text_input(
        "🔍 질문을 입력하세요",
        value=default_query,
        placeholder="예: 배포 순서가 어떻게 되나요?",
    )

    # 질문이 입력되면 RAG 파이프라인 실행
    if user_query:
        # 세션에서 이전에 사용한 질문값 초기화
        if "user_query" in st.session_state:
            del st.session_state["user_query"]

        if not info["exists"]:
            st.error("❌ 먼저 문서를 인덱싱해주세요. (사이드바 → Reindex)")
            return

        with st.spinner("문서를 검색하고 답변을 생성하는 중..."):
            try:
                result = ask(user_query)
            except Exception as e:
                st.error(f"❌ 오류가 발생했습니다: {e}")
                return

        # 답변 표시
        st.subheader("💬 답변")
        st.markdown(result["answer"])

        st.divider()

        # 검색 근거 표시
        st.subheader("📋 검색된 근거 문서")
        for i, source in enumerate(result["sources"]):
            with st.expander(
                f"근거 {i + 1}: {source['source_file']} "
                f"(chunk #{source['chunk_index']}, "
                f"거리: {source['distance']:.4f})"
            ):
                st.text(source["text"])


def main():
    render_sidebar()
    render_main()


if __name__ == "__main__":
    main()
