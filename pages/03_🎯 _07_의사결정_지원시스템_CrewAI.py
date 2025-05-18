import streamlit as st
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv
from openai import OpenAI
import base64
import requests
from typing import Dict, List, Any
# CrewAI 관련 import
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
from textwrap import dedent

# 환경 변수 로드
load_dotenv()

# OpenAI LLM 설정
llm = ChatOpenAI(
    model="gpt-4",
    temperature=0.7,
    openai_api_key=os.getenv('OPENAI_API_KEY')
)

# CrewAI 에이전트 정의
crew_roles = [
    {
        "key": "financial_agent",
        "role": "재무 전문가",
        "goal": "재무적 타당성 분석, ROI 및 현금흐름 예측, 리스크 평가, 투자 가치 분석을 수행한다.",
        "backstory": "수십 년 경력의 재무 전문가로, 기업의 재무 건전성과 투자 가치를 분석하는 데 탁월하다."
    },
    {
        "key": "legal_agent",
        "role": "법률 전문가",
        "goal": "법적 규제 검토, 계약 리스크, 규정 준수, 법적 대응 방안을 제시한다.",
        "backstory": "기업 법무팀장 출신으로, 복잡한 법률 이슈를 명확하게 분석한다."
    },
    {
        "key": "market_agent",
        "role": "시장 분석가",
        "goal": "시장 규모, 성장성, 경쟁사 분석, 진입장벽, 고객 니즈를 분석한다.",
        "backstory": "시장 트렌드 분석에 능한 전략 컨설턴트."
    },
    {
        "key": "tech_agent",
        "role": "기술 전문가",
        "goal": "기술적 실현 가능성, 트렌드, 필요 기술 스택, 기술 리스크를 평가한다.",
        "backstory": "최신 IT 트렌드와 기술 스택에 정통한 CTO 출신."
    },
    {
        "key": "risk_agent",
        "role": "리스크 관리자",
        "goal": "종합적 리스크 평가, 완화 방안, 비상 계획, 모니터링 방안을 제시한다.",
        "backstory": "위기관리 전문가로, 다양한 리스크를 체계적으로 관리한다."
    }
]

def create_crewai_agents(selected_roles):
    agents = []
    for role in crew_roles:
        if selected_roles.get(role["key"], False):
            agents.append(Agent(
                role=role["role"],
                goal=role["goal"],
                backstory=role["backstory"],
                llm=llm,
                allow_delegation=False,
                verbose=True
            ))
    return agents

def create_crewai_tasks(agents, title, description, options, reference_files):
    tasks = []
    for agent in agents:
        task_desc = dedent(f"""
        [{agent.role}]로서 아래 안건을 분석하세요.
        - 제목: {title}
        - 설명: {description}
        - 옵션: {options}
        {f'- 참고자료: {[f["filename"] for f in reference_files]}' if reference_files else ''}
        각 옵션의 장단점, 리스크, 추천 의견을 전문가 관점에서 제시하세요.
        """)
        tasks.append(Task(
            description=task_desc,
            expected_output="분석, 추천, 리스크 평가를 포함한 전문가 보고서",
            agent=agent
        ))
    return tasks

def analyze_with_crewai(title, description, options, reference_files, active_agents, debug_mode=False, model_name="gpt-4"):
    try:
        agents = create_crewai_agents(active_agents)
        if not agents:
            return {}
        tasks = create_crewai_tasks(agents, title, description, options, reference_files)
        crew = Crew(
            agents=agents,
            tasks=tasks,
            process=Process.sequential,
            verbose=debug_mode
        )
        results = crew.kickoff()
        # 결과를 에이전트별로 정리
        return {agent.role: results[i] for i, agent in enumerate(agents)}
    except Exception as e:
        st.error(f"CrewAI 분석 중 오류 발생: {str(e)}")
        return None

def connect_to_db():
    """MySQL DB 연결"""
    return mysql.connector.connect(
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        host=os.getenv('SQL_HOST'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )

def save_decision_case(title, description, decision_maker, created_by):
    """의사결정 안건 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO decision_cases 
            (title, description, decision_maker, created_by)
            VALUES (%s, %s, %s, %s)
        """, (title, description, decision_maker, created_by))
        
        case_id = cursor.lastrowid
        conn.commit()
        return case_id
    except Exception as e:
        st.error(f"안건 저장 중 오류 발생: {str(e)}")
        return None
    finally:
        cursor.close()
        conn.close()

def save_decision_option(case_id, option_data):
    """의사결정 옵션 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO decision_options 
            (case_id, option_name, advantages, disadvantages, 
             estimated_duration, priority, additional_info)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            case_id,
            option_data['name'],
            option_data['advantages'],
            option_data['disadvantages'],
            option_data['duration'],
            option_data['priority'],
            option_data.get('additional_info', '')
        ))
        
        conn.commit()
        return cursor.lastrowid
    finally:
        cursor.close()
        conn.close()

def save_ai_analysis(case_id, model_name, analysis_content, recommendation, risk_assessment):
    """AI 분석 결과 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO decision_ai_analysis 
            (case_id, model_name, analysis_content, recommendation, risk_assessment)
            VALUES (%s, %s, %s, %s, %s)
        """, (case_id, model_name, analysis_content, recommendation, risk_assessment))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"AI 분석 저장 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_decision_cases():
    """의사결정 안건 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM decision_cases 
            ORDER BY created_at DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_case_options(case_id):
    """안건의 옵션 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM decision_options 
            WHERE case_id = %s 
            ORDER BY priority
        """, (case_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_ai_analysis(case_id):
    """AI 분석 결과 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM decision_ai_analysis 
            WHERE case_id = %s 
            ORDER BY created_at DESC
        """, (case_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def update_case_status(case_id, status, final_option_id, final_comment):
    """의사결정 상태 업데이트"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE decision_cases 
            SET status = %s, 
                final_option_id = %s, 
                final_comment = %s,
                decided_at = NOW()
            WHERE case_id = %s
        """, (status, final_option_id, final_comment, case_id))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"상태 업데이트 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def read_markdown_file(uploaded_file):
    """업로드된 마크다운 파일 읽기"""
    try:
        content = uploaded_file.read().decode('utf-8')
        return {
            'filename': uploaded_file.name,
            'content': content
        }
    except Exception as e:
        st.error(f"파일 읽기 오류: {str(e)}")
        return None

def delete_decision_case(case_id):
    """의사결정 안건 삭제"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # 외래 키 제약 조건으로 인해 자동으로 관련 옵션과 AI 분석도 삭제됨
        cursor.execute("""
            DELETE FROM decision_cases 
            WHERE case_id = %s
        """, (case_id,))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"안건 삭제 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def save_reference_file(case_id, filename, content):
    """참고 자료 파일 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO decision_reference_files 
            (case_id, filename, file_content)
            VALUES (%s, %s, %s)
        """, (case_id, filename, content))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"파일 저장 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_reference_files(case_id):
    """참고 자료 파일 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT * FROM decision_reference_files 
            WHERE case_id = %s 
            ORDER BY created_at
        """, (case_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def format_options_for_analysis(options):
    """데이터베이스 옵션을 AI 분석용 형식으로 변환"""
    return [{
        'name': opt['option_name'],
        'advantages': opt['advantages'],
        'disadvantages': opt['disadvantages'],
        'duration': opt['estimated_duration'],
        'priority': opt['priority'],
        'additional_info': opt.get('additional_info', '')
    } for opt in options]

def main():
    st.title("🎯 의사결정 지원 시스템 (CrewAI 기반)")
    
    # 세션 상태 초기화
    if 'current_case_id' not in st.session_state:
        st.session_state.current_case_id = None
    if 'ai_analysis_results' not in st.session_state:
        st.session_state.ai_analysis_results = {}
    if 'options' not in st.session_state:
        st.session_state.options = []

    # 디버그 모드 설정
    debug_mode = st.sidebar.checkbox(
        "디버그 모드",
        help="에이전트와 태스크의 실행 과정을 자세히 표시합니다.",
        value=False
    )
    
    # 에이전트 선택
    with st.expander("🤖 AI 에이전트 설정"):
        st.subheader("활성화할 에이전트")
        col1, col2, col3 = st.columns(3)
        with col1:
            financial_agent = st.checkbox("재무 전문가", value=True)
            legal_agent = st.checkbox("법률 전문가", value=True)
            market_agent = st.checkbox("시장 분석가", value=True)
        with col2:
            risk_agent = st.checkbox("리스크 관리 전문가", value=True)
            tech_agent = st.checkbox("기술 전문가", value=True)
        with col3:
            hr_agent = st.checkbox("인사/조직 전문가", value=True)
            operation_agent = st.checkbox("운영 전문가", value=True)
            strategy_agent = st.checkbox("전략 전문가", value=True)
            integration_agent = st.checkbox("통합 매니저", value=True, disabled=True)

    # 활성화된 에이전트 정보 저장
    active_agents = {
        'financial_agent': financial_agent,
        'legal_agent': legal_agent,
        'market_agent': market_agent,
        'risk_agent': risk_agent,
        'tech_agent': tech_agent,
        'hr_agent': hr_agent,
        'operation_agent': operation_agent,
        'strategy_agent': strategy_agent,
        'integration_agent': True  # 항상 활성화
    }

    # 모델 선택 추가
    model_name = st.selectbox(
        "사용할 모델",
        ["gpt-4o-mini", "gpt-4"],
        index=0,  # gpt-4o-mini를 기본값으로
        help="분석에 사용할 AI 모델을 선택하세요"
    )

    tab1, tab2 = st.tabs(["의사결정 안건 등록", "의사결정 현황"])
    
    with tab1:
        st.header("새로운 의사결정 안건 등록")
        
        # 기본 정보 입력
        title = st.text_input("안건 제목")
        description = st.text_area("안건 설명")
        
        # 여러 마크다운 파일 업로드
        uploaded_files = st.file_uploader(
            "참고 자료 업로드 (여러 파일 선택 가능)", 
            type=['md', 'txt'],
            accept_multiple_files=True,
            help="추가 참고 자료가 있다면 마크다운(.md) 또는 텍스트(.txt) 파일로 업로드해주세요."
        )
        
        reference_files = []
        if uploaded_files:
            for uploaded_file in uploaded_files:
                file_data = read_markdown_file(uploaded_file)
                if file_data:
                    reference_files.append(file_data)
            
            if reference_files:
                with st.expander("업로드된 참고 자료 목록"):
                    for file in reference_files:
                        st.markdown(f"### 📄 {file['filename']}")
                        st.markdown(file['content'])
                        st.markdown("---")
        
        decision_maker = st.text_input("최종 의사결정자")
        created_by = st.text_input("작성자")
        
        # 옵션 입력
        st.subheader("의사결정 옵션")
        num_options = st.number_input("옵션 수", min_value=1, max_value=10, value=2)
        
        # 옵션 목록 업데이트
        if len(st.session_state.options) != num_options:
            st.session_state.options = [None] * num_options
        
        options = []
        for i in range(num_options):
            with st.expander(f"옵션 {i+1}"):
                option = {
                    'name': st.text_input(f"옵션 {i+1} 이름", key=f"name_{i}"),
                    'advantages': st.text_area(f"장점", key=f"adv_{i}"),
                    'disadvantages': st.text_area(f"단점", key=f"dis_{i}"),
                    'duration': st.text_input(f"예상 소요 기간", key=f"dur_{i}"),
                    'priority': st.number_input(f"우선순위", 1, 10, key=f"pri_{i}"),
                    'additional_info': st.text_area(f"추가 정보", key=f"add_{i}")
                }
                st.session_state.options[i] = option
                options.append(option)
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            if st.button("안건 저장", type="primary"):
                if title and description and decision_maker and created_by:
                    case_id = save_decision_case(title, description, decision_maker, created_by)
                    if case_id:
                        st.session_state.current_case_id = case_id
                        for option in options:
                            save_decision_option(case_id, option)
                        # 참고 자료 파일 저장
                        if reference_files:
                            for file in reference_files:
                                save_reference_file(
                                    case_id,
                                    file['filename'],
                                    file['content']
                                )
                        st.success("✅ 의사결정 안건이 저장되었습니다!")
                else:
                    st.error("모든 필수 항목을 입력해주세요.")
        
        with col2:
            if st.button("AI 분석 요청"):
                if not st.session_state.current_case_id:
                    st.error("먼저 안건을 저장해주세요.")
                    return
                
                if title and description and all(opt['name'] for opt in options):
                    with st.spinner("CrewAI가 분석중입니다..."):
                        analysis_results = analyze_with_crewai(
                            title,
                            description,
                            options,
                            reference_files if reference_files else None,
                            active_agents,
                            debug_mode,
                            model_name
                        )
                        
                        if analysis_results:
                            st.session_state.ai_analysis_results = analysis_results
                            st.success("✅ CrewAI 분석이 완료되었습니다!")
        
        # AI 분석 결과 표시 - 에이전트별 탭으로 구성
        if st.session_state.ai_analysis_results:
            st.write("### CrewAI 분석 결과")
            
            # 에이전트별 탭 생성
            agent_tabs = st.tabs([
                agent_name.replace('_', ' ').title() 
                for agent_name, is_active in active_agents.items() 
                if is_active
            ])
            
            for tab, (agent_name, analysis) in zip(
                agent_tabs, 
                {k: v for k, v in st.session_state.ai_analysis_results.items() 
                 if active_agents.get(k, False)}.items()
            ):
                with tab:
                    st.markdown(f"### {agent_name.replace('_', ' ').title()} 분석")
                    st.markdown(analysis)

    with tab2:
        st.header("의사결정 현황")
        
        # 안건 목록 조회
        cases = get_decision_cases()
        
        for case in cases:
            status_emoji = {
                'pending': '⏳',
                'approved': '✅',
                'rejected': '❌',
                'deferred': '⏸️'
            }.get(case['status'], '❓')
            
            with st.expander(f"{status_emoji} {case['title']} ({case['created_at'].strftime('%Y-%m-%d')})"):
                # 상단에 버튼들을 배치할 컬럼 추가
                col1, col2, col3 = st.columns([4, 1, 1])
                
                with col1:
                    st.write(f"**설명:** {case['description']}")
                    st.write(f"**의사결정자:** {case['decision_maker']}")
                    st.write(f"**상태:** {case['status'].upper()}")
                
                with col2:
                    # 추가 지침 입력 텍스트 박스를 먼저 표시
                    additional_instructions = st.text_area(
                        "재분석 시 참고할 추가 지침",
                        placeholder="예: 최근의 시장 변화를 고려해주세요. / ESG 관점에서 재검토해주세요. / 특정 위험 요소를 중점적으로 분석해주세요.",
                        help="AI가 재분석 시 특별히 고려해야 할 사항이나 관점을 입력해주세요.",
                        key=f"instructions_{case['case_id']}"
                    )
                    
                    # 분석 결과 저장 여부 선택 - 고유한 key 추가
                    save_analysis = st.checkbox(
                        "분석 결과를 DB에 저장", 
                        value=False,
                        key=f"save_analysis_{case['case_id']}"  # 고유한 key 추가
                    )
                    
                    # AI 재분석 버튼
                    if st.button("🤖 AI 재분석 시작", key=f"reanalyze_{case['case_id']}", type="primary"):
                        # 옵션 목록 가져오기
                        db_options = get_case_options(case['case_id'])
                        formatted_options = format_options_for_analysis(db_options)
                        reference_files = get_reference_files(case['case_id'])
                        
                        with st.spinner("AI가 재분석중입니다..."):
                            # 추가 지침을 포함한 프롬프트 생성
                            modified_description = f"""
                            {case['description']}

                            [추가 분석 지침]
                            {additional_instructions if additional_instructions.strip() else '일반적인 관점에서 분석해주세요.'}
                            """
                            
                            analysis_results = analyze_with_crewai(
                                case['title'],
                                modified_description,  # 수정된 설명 사용
                                formatted_options,
                                reference_files,
                                active_agents,
                                debug_mode,
                                model_name
                            )
                            
                            if analysis_results:
                                # 분석 결과 표시
                                st.write("### 새로운 분석 결과")
                                st.write(f"**분석 지침:** {additional_instructions}")
                                
                                # 에이전트별 탭 생성
                                agent_tabs = st.tabs([
                                    agent_name.replace('_', ' ').title() 
                                    for agent_name, is_active in active_agents.items() 
                                    if is_active
                                ])
                                
                                for tab, (agent_name, analysis) in zip(
                                    agent_tabs,
                                    {k: v for k, v in analysis_results.items() 
                                     if active_agents.get(k, False)}.items()
                                ):
                                    with tab:
                                        st.markdown(f"### {agent_name.replace('_', ' ').title()} 분석")
                                        st.markdown(analysis)
                                
                                # 사용자가 선택한 경우에만 DB에 저장
                                if save_analysis:
                                    for agent_type, analysis in analysis_results.items():
                                        # model_name 길이 제한
                                        model_name_str = f"AI {agent_type} ({model_name})"
                                        if additional_instructions.strip():
                                            model_name_str = f"{model_name_str} - {additional_instructions[:20]}..."
                                        
                                        # 최대 50자로 제한
                                        model_name_str = model_name_str[:50]
                                        
                                        save_ai_analysis(
                                            case['case_id'],
                                            model_name_str,
                                            analysis,
                                            '',
                                            ''
                                        )
                                    st.success("✅ 새로운 AI 분석이 DB에 저장되었습니다!")
                                
                                st.success("✅ AI 분석이 완료되었습니다!")
                
                with col3:
                    # 기존 삭제 버튼 로직
                    delete_checkbox = st.checkbox("삭제 확인", key=f"delete_confirm_{case['case_id']}")
                    if delete_checkbox:
                        if st.button("🗑️ 삭제", key=f"delete_{case['case_id']}", type="primary"):
                            if delete_decision_case(case['case_id']):
                                st.success("✅ 의사결정 안건이 삭제되었습니다.")
                                st.rerun()
                    else:
                        st.button("🗑️ 삭제", key=f"delete_{case['case_id']}", disabled=True)
                        st.caption("삭제하려면 먼저 체크박스를 선택하세요")

                # 옵션 목록 표시
                options = get_case_options(case['case_id'])
                st.write("### 옵션 목록")
                
                # 옵션들을 표 형태로 표시
                for opt in options:
                    is_selected = case['final_option_id'] == opt['option_id']
                    st.markdown(f"""
                    ### {'✅ ' if is_selected else ''}옵션 {opt['option_name']}
                    **우선순위:** {opt['priority']}
                    
                    **장점:**
                    {opt['advantages']}
                    
                    **단점:**
                    {opt['disadvantages']}
                    
                    **예상 기간:** {opt['estimated_duration']}
                    {f"**추가 정보:**\n{opt['additional_info']}" if opt.get('additional_info') else ''}
                    ---
                    """)
                
                # AI 분석 결과 표시
                analyses = get_ai_analysis(case['case_id'])
                if analyses:
                    st.write("### AI 분석 결과")
                    
                    # 각 분석 결과를 탭으로 표시
                    analysis_tabs = st.tabs([
                        f"분석 {idx} ({analysis['created_at'].strftime('%Y-%m-%d %H:%M')})" 
                        for idx, analysis in enumerate(analyses, 1)
                    ])
                    
                    for tab, analysis in zip(analysis_tabs, analyses):
                        with tab:
                            st.markdown(f"**모델:** {analysis['model_name']}")
                            
                            st.markdown("**분석 내용:**")
                            st.markdown(analysis['analysis_content'])
                            
                            if analysis['recommendation']:
                                st.markdown("**추천 의견:**")
                                st.markdown(analysis['recommendation'])
                            
                            if analysis['risk_assessment']:
                                st.markdown("**위험도 평가:**")
                                st.markdown(analysis['risk_assessment'])
                
                # 의사결정 입력 (pending 상태일 때만)
                if case['status'] == 'pending':
                    st.write("### 최종 의사결정")
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        decision_status = st.selectbox(
                            "결정 상태",
                            ['approved', 'rejected', 'deferred'],
                            key=f"status_{case['case_id']}"
                        )
                    
                    with col2:
                        selected_option = st.selectbox(
                            "선택된 옵션",
                            options,
                            format_func=lambda x: x['option_name'],
                            key=f"option_{case['case_id']}"
                        )
                    
                    final_comment = st.text_area(
                        "최종 코멘트",
                        key=f"comment_{case['case_id']}"
                    )
                    
                    if st.button("의사결정 확정", key=f"decide_{case['case_id']}", type="primary"):
                        if update_case_status(
                            case['case_id'],
                            decision_status,
                            selected_option['option_id'],
                            final_comment
                        ):
                            st.success("✅ 의사결정이 저장되었습니다!")
                            st.rerun()
                else:
                    if case['final_comment']:
                        st.write("### 최종 의사결정 내용")
                        st.write(case['final_comment'])

                # 참고 자료 파일 표시
                reference_files = get_reference_files(case['case_id'])
                if reference_files:
                    st.write("### 📎 참고 자료")
                    for file in reference_files:
                        st.markdown(f"""
                        #### 📄 {file['filename']}
                        ```
                        {file['file_content']}
                        ```
                        ---
                        """)

if __name__ == "__main__":
    main() 