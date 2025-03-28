import streamlit as st
import pandas as pd
from datetime import datetime
import mysql.connector
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_community.llms import LlamaCpp  # 로컬 LLM용
import json

load_dotenv()

def load_management_theories():
    """경영 이론 100가지 로드"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT theory_id as id, category, name, description
            FROM management_theories
            ORDER BY category, name
        """)
        
        theories = {}
        for row in cursor.fetchall():
            category = row['category']
            if category not in theories:
                theories[category] = []
            theories[category].append({
                'id': row['id'],
                'name': row['name'],
                'description': row['description']
            })
        
        return theories
        
    except Exception as e:
        st.error(f"경영 이론 로드 중 오류가 발생했습니다: {str(e)}")
        return {}
        
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def get_theory_description(theory_id):
    """선택된 이론에 대한 설명 반환"""
    theories = load_management_theories()
    for category, theory_list in theories.items():
        for theory in theory_list:
            if theory['id'] == theory_id:
                return theory['description']
    return ""

def get_llm():
    """LLM 모델 설정"""
    # LLM 선택 (기본값: OpenAI)
    llm_option = st.sidebar.selectbox(
        "🤖 AI 모델 선택",
        ["OpenAI GPT-4", "OpenAI GPT-3.5", "Local LLM"],
        index=1  # GPT-3.5를 기본값으로 설정
    )
    
    try:
        if llm_option == "Local LLM":
            # 로컬 LLM 설정
            if os.path.exists("models/llama-2-7b-chat.gguf"):
                return LlamaCpp(
                    model_path="models/llama-2-7b-chat.gguf",
                    temperature=0.7,
                    max_tokens=2000,
                    top_p=1,
                    verbose=True
                )
            else:
                st.error("로컬 LLM 모델 파일을 찾을 수 없습니다. OpenAI GPT-3.5를 사용합니다.")
                return ChatOpenAI(model="gpt-3.5-turbo")
        else:
            # OpenAI 모델 설정
            model_name = "gpt-4" if llm_option == "OpenAI GPT-4" else "gpt-3.5-turbo"
            return ChatOpenAI(
                api_key=os.getenv('OPENAI_API_KEY'),
                model=model_name,
                temperature=0.7
            )
    except Exception as e:
        st.error(f"LLM 초기화 중 오류 발생: {str(e)}")
        return None

def apply_framework_to_strategy(content, framework_id, framework_name):
    """선택된 프레임워크를 전략에 적용"""
    llm = get_llm()
    if not llm:
        st.error("AI 모델을 초기화할 수 없습니다.")
        return None
    
    prompt = f"""
    다음 사업 전략을 {framework_name} 프레임워크를 사용하여 재분석하고 수정해주세요:
    
    원본 전략:
    {content}
    
    {framework_name}의 주요 구성요소와 원칙을 적용하여 전략을 수정하되,
    다음 사항을 고려해주세요:
    1. 프레임워크의 핵심 개념을 명확히 반영
    2. 기존 전략의 주요 목표와 방향성 유지
    3. 실행 가능한 구체적 제안 포함
    
    결과는 다음 구조로 작성해주세요:
    1. 프레임워크 적용 배경
    2. 주요 분석 결과
    3. 수정된 전략
    4. 실행 계획
    """
    
    try:
        response = llm.invoke(prompt)
        return response.content if hasattr(response, 'content') else str(response)
    except Exception as e:
        st.error(f"전략 분석 중 오류 발생: {str(e)}")
        return None

# DB 연결 설정
def connect_to_db():
    return mysql.connector.connect(
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        host=os.getenv('SQL_HOST'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )

def save_framework_application(original, framework_id, modified):
    """프레임워크 적용 결과 저장"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor()
        
        # 현재 로그인한 사용자 ID (세션에서 가져오기)
        user_id = st.session_state.get('user_id', None)
        
        # framework_id가 정수형인지 확인
        try:
            framework_id = int(framework_id)
        except (TypeError, ValueError):
            st.error("프레임워크 ID가 올바르지 않습니다.")
            return False
        
        # 프레임워크 존재 여부 확인
        cursor.execute("SELECT COUNT(*) FROM management_theories WHERE theory_id = %s", (framework_id,))
        if cursor.fetchone()[0] == 0:
            st.error("선택한 프레임워크가 존재하지 않습니다.")
            return False
        
        cursor.execute("""
            INSERT INTO strategy_framework_applications 
            (original_strategy, framework_id, modified_strategy, created_by)
            VALUES (%s, %s, %s, %s)
        """, (original, framework_id, modified, user_id))
        
        conn.commit()
        return True
        
    except Exception as e:
        st.error(f"저장 중 오류가 발생했습니다: {str(e)}")
        return False
        
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def get_saved_strategies():
    """저장된 전략 목록 조회"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT 
                a.*,
                m.name as framework_name,
                m.description as framework_description,
                m.category as framework_category
            FROM strategy_framework_applications a
            INNER JOIN management_theories m 
                ON a.framework_id = m.theory_id
            ORDER BY a.created_at DESC
        """)
        
        strategies = cursor.fetchall()
        return strategies
        
    except Exception as e:
        st.error(f"전략 조회 중 오류가 발생했습니다: {str(e)}")
        return []
        
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

def main():
    st.title("🎯 전략 프레임워크 적용")
    
    # 세션 상태 초기화
    if 'modified_strategy' not in st.session_state:
        st.session_state.modified_strategy = None
    if 'current_content' not in st.session_state:
        st.session_state.current_content = None
    if 'selected_theory_id' not in st.session_state:
        st.session_state.selected_theory_id = None
    
    tab1, tab2 = st.tabs(["전략 프레임워크 적용", "저장된 전략 조회"])
    
    with tab1:
        uploaded_file = st.file_uploader(
            "전략 문서 업로드",
            type=['txt', 'md', 'pdf'],
            help="텍스트, 마크다운 또는 PDF 형식의 전략 문서를 업로드하세요."
        )
        
        if uploaded_file:
            if uploaded_file.type == "application/pdf":
                # PDF 처리 로직
                pass
            else:
                content = uploaded_file.read().decode('utf-8')
                st.session_state.current_content = content
            
            st.subheader("📄 원본 전략")
            st.markdown(st.session_state.current_content)
            
            # 프레임워크 선택 UI
            st.subheader("🎯 프레임워크 선택")
            
            # 메인 카테고리 선택
            main_categories = [
                "경영 전략",
                "마케팅",
                "조직 관리",
                "리더십",
                "운영 관리",
                "혁신과 창의성",
                "재무 관리",
                "인사 관리",
                "경영 정보 시스템",
                "기타 경영 이론"
            ]
            
            selected_category = st.selectbox(
                "프레임워크 분야 선택",
                main_categories,
                index=0
            )
            
            # 선택된 카테고리의 프레임워크 목록 표시
            theories = load_management_theories()
            if selected_category in theories:
                framework_options = [(t['id'], t['name']) for t in theories[selected_category]]
                
                selected_theory_id = st.selectbox(
                    "세부 프레임워크 선택",
                    options=[id for id, _ in framework_options],
                    format_func=lambda x: next(name for id, name in framework_options if id == x)
                )
                st.session_state.selected_theory_id = selected_theory_id
                
                if selected_theory_id:
                    # 선택된 프레임워크 설명 표시
                    theory_desc = get_theory_description(selected_theory_id)
                    with st.info("**선택된 프레임워크 설명**"):
                        st.markdown(theory_desc)
                    
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        if st.button("프레임워크 적용", key="apply_framework"):
                            with st.spinner("프레임워크를 적용하여 전략을 수정하고 있습니다..."):
                                theory_name = next(name for id, name in framework_options if id == selected_theory_id)
                                modified = apply_framework_to_strategy(
                                    st.session_state.current_content,
                                    selected_theory_id,
                                    theory_name
                                )
                                st.session_state.modified_strategy = modified
                    
                    # 수정된 전략이 있을 때만 표시
                    if st.session_state.modified_strategy:
                        st.subheader("📝 수정된 전략")
                        st.markdown(st.session_state.modified_strategy)
                        
                        if st.button("💾 전략 저장", key="save_strategy"):
                            success = save_framework_application(
                                st.session_state.current_content,
                                st.session_state.selected_theory_id,
                                st.session_state.modified_strategy
                            )
                            if success:
                                st.success("전략이 성공적으로 저장되었습니다!")
                                st.session_state.modified_strategy = None
                                st.session_state.current_content = None
                                st.session_state.selected_theory_id = None
                                st.rerun()

    with tab2:
        st.header("📚 저장된 전략 목록")
        
        strategies = get_saved_strategies()
        
        if strategies:
            for strategy in strategies:
                with st.expander(
                    f"📄 적용일시: {strategy['created_at'].strftime('%Y-%m-%d %H:%M')} | "
                    f"프레임워크: {strategy['framework_category']} - {strategy['framework_name']}"
                ):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("원본 전략")
                        st.markdown(strategy['original_strategy'])
                    
                    with col2:
                        st.subheader(f"수정된 전략 ({strategy['framework_name']})")
                        with st.info("**적용된 프레임워크 설명**"):
                            st.markdown(strategy['framework_description'])
                        st.markdown(strategy['modified_strategy'])
                    
                    st.divider()
        else:
            st.info("저장된 전략이 없습니다.")

if __name__ == "__main__":
    main() 