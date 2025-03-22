import streamlit as st
import pandas as pd
from datetime import datetime
import mysql.connector
import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_community.llms import LlamaCpp  # 로컬 LLM용
from crewai import Agent, Task, Crew, Process
import json
import time

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

def save_framework_application(original_content, framework_info, modified_content):
    """프레임워크 적용 결과 저장"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor()
        
        # 문자열로 변환하여 저장
        if not isinstance(modified_content, str):
            modified_content = str(modified_content)
        
        # 현재 로그인한 사용자 ID
        user_id = st.session_state.get('user_id', None)
        
        # 프레임워크 이름들을 결합하여 하나의 문자열로 저장
        framework_names = [f['name'] for f in framework_info]
        combined_frameworks = " + ".join(framework_names)
        
        # 현재 시간을 파일명으로 생성 (표시용)
        current_time = datetime.now().strftime('%Y%m%d_%H%M%S')
        display_name = f"사업전략보고서_{current_time}"
        
        # 하나의 통합된 레코드로 저장
        cursor.execute("""
            INSERT INTO strategy_framework_applications 
            (original_strategy, framework_id, modified_strategy, created_by, created_at)
            VALUES (%s, %s, %s, %s, NOW())
        """, (
            original_content,
            framework_info[0]['id'],  # 대표 프레임워크 ID
            modified_content,
            user_id
        ))
        
        conn.commit()
        st.success(f"'{display_name}' 파일로 저장되었습니다! (적용 프레임워크: {combined_frameworks})")
        return True
        
    except Exception as e:
        st.error(f"전략 저장 중 오류 발생: {str(e)}")
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
                a.application_id,
                a.original_strategy,
                a.modified_strategy,
                a.created_at,
                a.created_by,
                CONCAT('사업전략보고서_', DATE_FORMAT(a.created_at, '%Y%m%d_%H%i%s')) as file_name,
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
    
    # 디버그 모드 설정
    debug_mode = st.sidebar.checkbox(
        "디버그 모드",
        help="에이전트와 태스크의 실행 과정을 자세히 표시합니다.",
        value=False
    )
    
    # CrewAI 설정
    with st.expander("🤖 AI 에이전트 설정"):
        use_crewai = st.checkbox("CrewAI 멀티 에이전트 사용", value=True)
        
        if use_crewai:
            st.subheader("활성화할 에이전트")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                framework_expert = st.checkbox("프레임워크 전문가", value=True)
                market_agent = st.checkbox("시장 분석 에이전트", value=True)
                strategy_agent = st.checkbox("전략 기획 에이전트", value=True)
                
            with col2:
                business_agent = st.checkbox("비즈니스 모델 에이전트", value=True)
                innovation_agent = st.checkbox("혁신 전략 에이전트", value=True)
                risk_agent = st.checkbox("리스크 관리 에이전트", value=True)
                
            with col3:
                implementation_agent = st.checkbox("실행 계획 전문가", value=True)
                integration_agent = st.checkbox("전략 통합 전문가", value=True)
                evaluation_agent = st.checkbox("성과 평가 전문가", value=True)

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
                # 프레임워크 옵션 생성
                framework_options = []
                for theory in theories[selected_category]:
                    framework_options.append({
                        'id': theory['id'],
                        'name': theory['name'],
                        'description': theory['description']
                    })
                
                # 다중 선택으로 변경
                selected_framework_names = st.multiselect(
                    "세부 프레임워크 선택 (복수 선택 가능)",
                    options=[f['name'] for f in framework_options],
                    help="분석에 사용할 프레임워크를 여러 개 선택할 수 있습니다."
                )
                
                if selected_framework_names:
                    # 선택된 프레임워크 정보 저장
                    framework_info = []
                    selected_theory_ids = []  # 선택된 프레임워크 ID 저장
                    
                    for name in selected_framework_names:
                        try:
                            framework = next(f for f in framework_options if f['name'] == name)
                            framework_info.append(framework)
                            selected_theory_ids.append(framework['id'])  # ID 저장
                            with st.info(f"**{framework['name']}**"):
                                st.markdown(framework['description'])
                        except StopIteration:
                            st.error(f"프레임워크 '{name}'를 찾을 수 없습니다.")
                            continue
                    
                    # 세션 상태에 선택된 프레임워크 ID 저장
                    st.session_state.selected_theory_ids = selected_theory_ids
                    
                    if framework_info:  # 유효한 프레임워크가 하나 이상 있을 때만 진행
                        col1, col2 = st.columns([1, 2])
                        with col1:
                            if st.button("프레임워크 적용", key="apply_framework"):
                                with st.spinner("프레임워크를 적용하여 전략을 수정하고 있습니다..."):
                                    if use_crewai:
                                        modified = apply_framework_with_crewai(
                                            st.session_state.current_content,
                                            framework_info,
                                            {
                                                'framework_expert': framework_expert,
                                                'market_agent': market_agent,
                                                'strategy_agent': strategy_agent,
                                                'business_agent': business_agent,
                                                'innovation_agent': innovation_agent,
                                                'risk_agent': risk_agent,
                                                'implementation_agent': implementation_agent,
                                                'integration_agent': integration_agent,
                                                'evaluation_agent': evaluation_agent
                                            },
                                            debug_mode
                                        )
                                    else:
                                        # 단일 프레임워크 처리 (기존 방식)
                                        modified = apply_framework_to_strategy(
                                            st.session_state.current_content,
                                            selected_theory_ids[0],  # 첫 번째 프레임워크 ID 사용
                                            framework_info[0]['name']
                                        )
                                    st.session_state.modified_strategy = modified
                        
                        # 수정된 전략이 있을 때만 표시
                        if st.session_state.modified_strategy:
                            st.subheader("📝 수정된 전략")
                            st.markdown(st.session_state.modified_strategy)
                            
                            # 저장 버튼 클릭 시
                            if st.button("💾 전략 저장", key="save_strategy"):
                                try:
                                    success = save_framework_application(
                                        st.session_state.current_content,
                                        framework_info,
                                        st.session_state.modified_strategy
                                    )
                                    
                                except Exception as e:
                                    st.error(f"전략 저장 중 오류 발생: {str(e)}")

    with tab2:
        st.header("📚 저장된 사업 전략 보고서 목록")
        
        strategies = get_saved_strategies()
        
        if strategies:
            for strategy in strategies:
                with st.expander(
                    f"📄 {strategy['file_name']} | "
                    f"프레임워크: {strategy['framework_category']} - {strategy['framework_name']}"
                ):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("원본 전략")
                        st.markdown(strategy['original_strategy'])
                    
                    with col2:
                        st.subheader("사업 전략 보고서")
                        with st.info("**적용된 프레임워크 설명**"):
                            st.markdown(strategy['framework_description'])
                        st.markdown(strategy['modified_strategy'])
                    
                    st.divider()
        else:
            st.info("저장된 전략 보고서가 없습니다.")

def apply_framework_with_crewai(content, framework_info, active_agents, debug_mode=False):
    try:
        if debug_mode:
            st.write("### 🚀 CrewAI 실행 시작")
            st.write(f"📌 선택된 프레임워크: {', '.join(f['name'] for f in framework_info)}")
            st.write("### 📊 분석 단계")
            st.write("""
            1. 프로젝트 초기화
            2. 프레임워크별 분석
            3. 전문가별 심층 분석
            4. 통합 분석
            5. 최종 보고서 작성
            """)
            
            progress_bar = st.progress(0)
            status_text = st.empty()
        
        # LLM 설정
        if debug_mode:
            st.write("### 🤖 AI 모델 초기화")
            st.write("- 모델: GPT-4")
            st.write("- 온도: 0.7")
        
        llm = ChatOpenAI(
            api_key=os.getenv('OPENAI_API_KEY'),
            model="gpt-4o-mini",
            temperature=0.7
        )
        
        # 에이전트 생성
        if debug_mode:
            st.write("### 👥 에이전트 생성 시작")
            st.write(f"- 프레임워크 전문가: {len(framework_info)}명")
            st.write("- 매니저 에이전트: 1명")
            st.write("- 보고서 전문가: 1명")
            active_count = sum(1 for v in active_agents.values() if v)
            st.write(f"- 활성화된 전문가: {active_count}명")
        
        agents = create_framework_agents(llm, framework_info, active_agents, debug_mode)
        
        if debug_mode:
            st.write(f"✅ 총 {len(agents)}명의 에이전트 생성 완료")
        
        # 태스크 생성
        if debug_mode:
            st.write("### 📋 태스크 생성 시작")
            st.write("""
            태스크 생성 순서:
            1. 프로젝트 초기화 태스크
            2. 프레임워크별 분석 태스크
            3. 전문가별 분석 태스크
            4. 통합 분석 태스크
            5. 최종 보고서 작성 태스크
            """)
        
        tasks = create_framework_tasks(agents, content, framework_info, debug_mode)
        
        # 태스크 유형별 개수 계산
        task_counts = {
            'framework': len([t for t in tasks if "프레임워크" in t.description]),
            'expert': len([t for t in tasks if "전문가" in t.description]),
            'total': len(tasks)
        }
        
        if debug_mode:
            st.write("### ✅ 태스크 생성 완료")
            st.write(f"- 총 태스크 수: {task_counts['total']}")
            st.write(f"- 프레임워크 태스크: {task_counts['framework']}개")
            st.write(f"- 전문가 태스크: {task_counts['expert']}개")
            st.write("- 통합 보고서 태스크: 1개")
        
        # Crew 실행 중 진행 상황 표시
        if debug_mode:
            st.write("### ⚙️ 분석 진행 상황")
            
            # 프로젝트 초기화
            status_text.text("프로젝트 초기화 중...")
            progress_bar.progress(10)
            
            # 프레임워크별 분석
            for i, framework in enumerate(framework_info):
                status_text.text(f"{framework['name']} 분석 중...")
                progress = 20 + (i * 10)
                progress_bar.progress(progress)
                
                st.write(f"🔍 {framework['name']} 분석:")
                st.write("- 구성요소별 분석 진행")
                st.write("- 현황 진단 수행")
                st.write("- 전략적 시사점 도출")
                st.write("- 개선 방안 수립")
                
            # 전문가별 분석
            status_text.text("전문가별 심층 분석 중...")
            progress_bar.progress(60)
            
            st.write("👥 전문가별 분석:")
            for agent_type in active_agents:
                if active_agents[agent_type]:
                    st.write(f"- {agent_type} 분석 진행")
            
            # 통합 분석
            status_text.text("분석 결과 통합 중...")
            progress_bar.progress(80)
            
            st.write("🔄 통합 분석:")
            st.write("- 프레임워크 간 시너지 도출")
            st.write("- 전략적 시사점 통합")
            st.write("- 실행 계획 조정")
            
            # 최종 보고서 작성
            status_text.text("최종 보고서 작성 중...")
            progress_bar.progress(90)
            
            st.write("📝 보고서 작성:")
            st.write("- 분석 결과 정리")
            st.write("- 전략 방향 수립")
            st.write("- 실행 계획 상세화")
        
        # Crew 실행
        crew = Crew(
            agents=agents,
            tasks=tasks,
            verbose=debug_mode
        )
        
        result = crew.kickoff()
        
        if debug_mode:
            status_text.text("분석 완료!")
            progress_bar.progress(100)
            
            st.write("### ✅ 분석 완료")
            st.write("- 결과 데이터 변환 중...")
        
        # CrewOutput을 문자열로 변환
        if hasattr(result, 'raw_output'):
            output = str(result.raw_output)
        elif hasattr(result, 'output'):
            output = str(result.output)
        else:
            output = str(result)
        
        if debug_mode:
            st.write("### 📊 결과 통계")
            st.write(f"- 총 문자 수: {len(output)}")
            st.write(f"- 섹션 수: {output.count('##')}")
            st.write(f"- 프레임워크 분석: {len(framework_info)}개")
            st.write(f"- 전문가 의견: {sum(1 for v in active_agents.values() if v)}개")
            st.write("✅ 전략 보고서 생성 완료")
        
        return output
        
    except Exception as e:
        if debug_mode:
            st.error("### 🚨 오류 발생")
            st.error(f"- 오류 유형: {type(e).__name__}")
            st.error(f"- 오류 메시지: {str(e)}")
            st.error(f"- 오류 위치: {e.__traceback__.tb_frame.f_code.co_filename}:{e.__traceback__.tb_lineno}")
            st.error("- 실행 중이던 작업: " + status_text.text)
        else:
            st.error(f"CrewAI 실행 중 오류 발생: {str(e)}")
        return None

def create_framework_agents(llm, framework_info, active_agents, debug_mode=False):
    """프레임워크 적용을 위한 에이전트 생성"""
    agents = []
    
    if debug_mode:
        st.write("### 🤖 에이전트 생성 시작")
    
    # 매니저 에이전트 (항상 포함)
    manager_agent = Agent(
        role="전략 프로젝트 매니저",
        goal="전체 분석 프로세스 조율 및 통합 관리",
        backstory=f"당신은 수많은 전략 프로젝트를 성공적으로 이끈 시니어 프로젝트 매니저입니다. 특히 {', '.join(f['name'] for f in framework_info)} 프레임워크를 활용한 전략 수립에 전문성이 있습니다.",
        verbose=debug_mode,
        llm=llm
    )
    agents.append(manager_agent)
    
    # 각 프레임워크별 전문가 에이전트 생성
    for framework in framework_info:
        if debug_mode:
            st.write(f"✨ {framework['name']} 전문가 에이전트 생성")
        
        framework_expert = Agent(
            role=f"{framework['name']} 전문가",
            goal=f"{framework['name']}를 활용한 전략 분석 및 개선",
            backstory=f"당신은 {framework['name']}의 전문가로서 다양한 기업의 전략 수립을 지원한 경험이 풍부합니다. 프레임워크에 대한 설명: {framework['description']}",
            verbose=debug_mode,
            llm=llm
        )
        agents.append(framework_expert)
    
    # 기능별 전문가 에이전트 설정
    agent_configs = {
        'market_agent': {
            'role': "시장 분석가",
            'goal': "시장 동향과 경쟁 환경 분석",
            'backstory': "시장 조사 및 경쟁 분석 전문가로서 다양한 산업의 시장 분석 경험이 있습니다."
        },
        'strategy_agent': {
            'role': "전략 기획가",
            'goal': "전략적 방향성 수립 및 실행 계획 수립",
            'backstory': "전략 컨설턴트로서 다수의 기업 전략 수립 프로젝트를 성공적으로 수행했습니다."
        },
        'business_agent': {
            'role': "비즈니스 모델 전문가",
            'goal': "비즈니스 모델 분석 및 최적화",
            'backstory': "비즈니스 모델 혁신 전문가로서 다양한 산업의 비즈니스 모델을 설계하고 개선한 경험이 있습니다."
        },
        'innovation_agent': {
            'role': "혁신 전략가",
            'goal': "혁신 기회 발굴 및 전략 수립",
            'backstory': "혁신 전략 전문가로서 기업의 혁신 프로젝트를 성공적으로 이끈 경험이 풍부합니다."
        },
        'risk_agent': {
            'role': "리스크 관리 전문가",
            'goal': "리스크 식별 및 대응 전략 수립",
            'backstory': "리스크 관리 전문가로서 다양한 기업의 리스크를 분석하고 관리한 경험이 있습니다."
        },
        'implementation_agent': {
            'role': "실행 계획 전문가",
            'goal': "실행 가능한 상세 계획 수립",
            'backstory': "프로젝트 실행 전문가로서 전략을 실질적인 행동 계획으로 변환한 경험이 풍부합니다."
        },
        'integration_agent': {
            'role': "전략 통합 전문가",
            'goal': "다양한 전략 요소의 통합 및 조화",
            'backstory': "전략 통합 전문가로서 복잡한 전략을 일관된 체계로 통합한 경험이 있습니다."
        },
        'evaluation_agent': {
            'role': "성과 평가 전문가",
            'goal': "성과 지표 설정 및 평가 체계 수립",
            'backstory': "성과 관리 전문가로서 전략 실행의 효과성을 측정하고 평가한 경험이 풍부합니다."
        }
    }
    
    # 선택된 에이전트 생성
    for agent_key, config in agent_configs.items():
        if active_agents.get(agent_key, False):
            if debug_mode:
                st.write(f"✨ {config['role']} 에이전트 생성")
            
            agent = Agent(
                role=config['role'],
                goal=config['goal'],
                backstory=config['backstory'],
                verbose=debug_mode,
                llm=llm
            )
            agents.append(agent)
    
    # 전략 보고서 작성 전문가 (항상 포함)
    report_agent = Agent(
        role="전략 보고서 전문가",
        goal="종합적인 사업전략 보고서 작성",
        backstory="당신은 전략 보고서 작성의 전문가로서, 복잡한 분석 결과를 명확하고 실행 가능한 전략 보고서로 변환하는 능력이 탁월합니다.",
        verbose=debug_mode,
        llm=llm
    )
    agents.append(report_agent)
    
    return agents

def create_framework_tasks(agents, content, framework_info, debug_mode=False):
    """프레임워크 적용을 위한 태스크 생성"""
    all_tasks = []
    
    # 각 프레임워크별 상세 분석 태스크 생성
    for i, framework in enumerate(framework_info):
        framework_task = Task(
            description=f"""
            {framework['name']} 프레임워크를 사용하여 다음과 같은 상세 분석을 수행하세요:
            
            [원본 전략]
            {content}
            
            프레임워크 설명: {framework['description']}
            
            분석 요구사항 (최소 15,000자):
            1. 프레임워크 구성요소별 상세 분석
            - 각 구성요소의 정의와 의미
            - 현재 상황 진단
            - 개선 기회 도출
            - 구체적 실행 방안
            
            2. 정량적/정성적 분석
            - 시장 데이터 분석
            - 경쟁사 벤치마킹
            - 고객 니즈 분석
            - 내부 역량 평가
            
            3. 전략적 시사점 도출
            - 핵심 발견사항
            - 전략적 기회
            - 위험 요소
            - 대응 방안
            
            4. 실행 계획 수립
            - 단기 과제 (90일)
            - 중기 과제 (1년)
            - 장기 과제 (3년)
            - 필요 자원과 예산
            
            5. 성과 관리 방안
            - KPI 설정
            - 모니터링 체계
            - 피드백 루프
            - 조정 메커니즘
            
            각 섹션은 다음을 포함해야 합니다:
            1. 구체적인 데이터와 수치
            2. 실제 사례와 벤치마킹
            3. 상세한 실행 계획
            4. 예상 효과와 리스크
            """,
            expected_output=f"""
            # {framework['name']} 프레임워크 분석 보고서

            ## 1. 프레임워크 구성요소별 상세 분석
            - 각 구성요소의 정의와 의미
            - 현재 상황 진단
            - 개선 기회 도출
            - 구체적 실행 방안

            ## 2. 정량적/정성적 분석
            - 시장 데이터 분석
            - 경쟁사 벤치마킹
            - 고객 니즈 분석
            - 내부 역량 평가

            ## 3. 전략적 시사점
            - 핵심 발견사항
            - 전략적 기회
            - 위험 요소
            - 대응 방안

            ## 4. 실행 계획
            - 단기 과제 (90일)
            - 중기 과제 (1년)
            - 장기 과제 (3년)
            - 필요 자원과 예산

            ## 5. 성과 관리 방안
            - KPI 설정
            - 모니터링 체계
            - 피드백 루프
            - 조정 메커니즘
            """,
            agent=agents[i+1]
        )
        all_tasks.append(framework_task)
    
    # 최종 통합 보고서 태스크
    final_report_task = Task(
        description=f"""
        선택된 프레임워크({', '.join(f['name'] for f in framework_info)})의 분석 결과를 통합하여 
        매우 상세하고 실행 가능한 사업 전략 보고서를 작성하세요.
        
        [원본 전략]
        {content}
        
        보고서 구성 (총 분량 최소 80,000자):
        
        1. Executive Summary (최소 5,000자)
        - 전략적 상황 개요
        - 프레임워크별 주요 발견사항
        - 통합 전략 방향
        - 핵심 실행 과제
        - 기대 효과
        
        2. 프레임워크별 심층 분석 (각 프레임워크별 최소 15,000자)
        [각 프레임워크별로 다음 내용 포함]
        - 프레임워크 개요와 적용 목적
        - 구성요소별 상세 분석
        - 현황 진단과 갭 분석
        - 개선 방향과 목표
        - 실행 전략과 과제
        - 기대 효과와 리스크
        
        3. 프레임워크 통합 분석 (최소 10,000자)
        - 프레임워크 간 연계성 분석
        - 시너지 효과 도출
        - 상충 요소 조정
        - 통합 실행 계획
        
        4. 전략적 실행 계획 (최소 15,000자)
        - 90일 실행 계획
          * 핵심 과제별 상세 계획
          * 책임자와 역할
          * 필요 자원과 예산
          * 성과 지표
        
        - 1년 실행 계획
          * 전략 과제 로드맵
          * 조직 변화 계획
          * 자원 배분 전략
          * 리스크 관리 방안
        
        - 3년 실행 계획
          * 장기 전략 목표
          * 단계별 성장 전략
          * 투자 계획
          * 조직 발전 방향
        
        5. 영역별 상세 전략 (각 영역별 최소 5,000자)
        - 마케팅 전략
        - 영업/판매 전략
        - 운영 전략
        - 조직/인사 전략
        - 재무 전략
        - 리스크 관리 전략
        - R&D/혁신 전략
        - 디지털 전환 전략
        
        6. 성과 관리 체계 (최소 5,000자)
        - KPI 체계와 목표
        - 모니터링 방안
        - 성과 평가 체계
        - 보상 연계 방안
        - 피드백 및 개선
        
        특별 요구사항:
        1. 모든 프레임워크의 핵심 개념이 전략에 반영되어야 함
        2. 각 실행 과제는 구체적이고 측정 가능해야 함
        3. 모든 제안에 대한 근거와 기대효과 제시
        4. 리스크 요인과 대응 방안 포함
        5. 실제 사례와 데이터 기반의 분석 포함
        
        결과물 형식:
        - 체계적인 목차와 구조
        - 시각적 자료 (차트, 표) 활용
        - 구체적 수치와 데이터 제시
        - 실행 가능한 액션 아이템
        - 명확한 책임과 일정
        """,
        expected_output="""
        # 통합 사업 전략 보고서

        ## 1. Executive Summary
        - 전략적 상황 개요
        - 프레임워크별 주요 발견사항
        - 통합 전략 방향
        - 핵심 실행 과제
        - 기대 효과

        ## 2. 프레임워크별 심층 분석
        [각 프레임워크별 상세 분석 결과]

        ## 3. 프레임워크 통합 분석
        - 프레임워크 간 연계성
        - 시너지 효과
        - 상충 요소 조정
        - 통합 실행 계획

        ## 4. 전략적 실행 계획
        ### 4.1 90일 실행 계획
        ### 4.2 1년 실행 계획
        ### 4.3 3년 실행 계획

        ## 5. 영역별 상세 전략
        - 마케팅 전략
        - 영업/판매 전략
        - 운영 전략
        - 조직/인사 전략
        - 재무 전략
        - 리스크 관리 전략
        - R&D/혁신 전략
        - 디지털 전환 전략

        ## 6. 성과 관리 체계
        - KPI 체계와 목표
        - 모니터링 방안
        - 성과 평가 체계
        - 보상 연계 방안
        - 피드백 및 개선
        """,
        agent=agents[-1]
    )
    all_tasks.append(final_report_task)
    
    return all_tasks

if __name__ == "__main__":
    main() 