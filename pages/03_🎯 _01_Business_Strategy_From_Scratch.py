import streamlit as st
import pandas as pd
from datetime import datetime
import mysql.connector
import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI
import json
from pydantic import BaseModel, Field
from typing import List, Dict, Any

load_dotenv()

# MySQL 연결 설정
def connect_to_db():
    return mysql.connector.connect(
        user=os.getenv('SQL_USER'),
        password=os.getenv('SQL_PASSWORD'),
        host=os.getenv('SQL_HOST'),
        database=os.getenv('SQL_DATABASE_NEWBIZ'),
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci'
    )

# AI 에이전트 정의
def create_agents(selected_agents, active_frameworks, debug_mode=False):
    """선택된 프레임워크와 에이전트에 따라 AI 에이전트 생성"""
    agents = []
    
    # OpenAI 모델 설정
    llm = ChatOpenAI(
        api_key=os.getenv('OPENAI_API_KEY'),
        model=os.getenv('MODEL_NAME', 'gpt-4'),
        temperature=0.7
    )

    # 프레임워크 전문가 에이전트 생성
    if debug_mode:
        st.write("### 🔧 프레임워크 전문가 에이전트 생성 중...")
    
    framework_experts = {
        "SWOT 분석": {
            "role": "SWOT 분석 전문가",
            "goal": "기업의 강점, 약점, 기회, 위협 요인을 체계적으로 분석",
            "backstory": "20년 경력의 전략 컨설턴트로서 수많은 기업의 SWOT 분석을 수행했습니다."
        },
        "블루오션 전략": {
            "role": "블루오션 전략가",
            "goal": "가치 혁신을 통한 새로운 시장 창출 전략 수립",
            "backstory": "블루오션 전략 전문가로서 다수의 혁신적인 비즈니스 모델을 개발했습니다."
        },
        "포터의 5가지 힘": {
            "role": "산업구조 분석가",
            "goal": "산업의 경쟁 구조와 역학 관계 분석",
            "backstory": "산업 분석 전문가로서 다양한 산업의 구조적 특성을 분석해왔습니다."
        },
        "비즈니스 모델 캔버스": {
            "role": "비즈니스 모델 전문가",
            "goal": "혁신적인 비즈니스 모델 설계",
            "backstory": "비즈니스 모델 혁신 전문가로서 수많은 스타트업의 성공을 지원했습니다."
        },
        "마케팅 믹스(4P)": {
            "role": "마케팅 전략가",
            "goal": "효과적인 마케팅 믹스 전략 수립",
            "backstory": "마케팅 전문가로서 제품, 가격, 유통, 촉진 전략을 통합적으로 설계해왔습니다."
        },
        "STP 전략": {
            "role": "시장 세분화 전문가",
            "goal": "효과적인 시장 세분화와 타겟팅 전략 수립",
            "backstory": "시장 세분화 전문가로서 정교한 타겟팅 전략을 수립해왔습니다."
        }
    }

    # 선택된 프레임워크별 전문가 에이전트 생성
    for framework in active_frameworks:
        if framework['name'] in framework_experts:
            expert = framework_experts[framework['name']]
            agent = Agent(
                role=expert['role'],
                goal=expert['goal'],
                backstory=expert['backstory'],
                verbose=debug_mode,
                llm=llm
            )
            agents.append(agent)
            if debug_mode:
                st.write(f"✅ {expert['role']} 생성됨")

    # 기능별 전문가 에이전트 생성
    functional_experts = {
        "market_analyst": {
            "role": "시장 분석가",
            "goal": "시장 동향과 경쟁 환경을 분석하여 실행 가능한 통찰 제공",
            "backstory": "20년 경력의 시장 분석 전문가로서 산업 동향을 정확히 파악하고 경쟁사 분석을 통해 실질적인 시장 기회를 발견하는 것이 특기입니다."
        },
        "strategy_consultant": {
            "role": "전략 컨설턴트",
            "goal": "비즈니스 전략 수립 및 실행 계획 개발",
            "backstory": "글로벌 컨설팅 펌에서 15년간 전략 컨설팅을 해온 전문가로서 복잡한 비즈니스 문제를 체계적으로 분석하고 실행 가능한 해결책을 제시합니다."
        },
        "marketing_expert": {
            "role": "마케팅 전문가",
            "goal": "효과적인 마케팅 및 판매 전략 수립",
            "backstory": "디지털 마케팅과 브랜드 전략 전문가로서 혁신적인 마케팅 캠페인을 성공적으로 이끌어왔습니다."
        },
        "financial_analyst": {
            "role": "재무 분석가",
            "goal": "재무적 실행 가능성 분석 및 투자 계획 수립",
            "backstory": "투자 은행과 벤처 캐피탈에서 12년간 일한 재무 전문가로서 사업의 수익성과 재무적 리스크를 정확히 분석합니다."
        },
        "operations_expert": {
            "role": "운영 전문가",
            "goal": "운영 효율성 및 프로세스 최적화",
            "backstory": "운영 최적화 전문가로서 다양한 산업의 프로세스 혁신을 성공적으로 이끌어왔습니다."
        },
        "risk_manager": {
            "role": "리스크 관리자",
            "goal": "리스크 식별 및 대응 전략 수립",
            "backstory": "리스크 관리 전문가로서 기업의 위험 요소를 체계적으로 분석하고 관리해왔습니다."
        }
    }

    # 선택된 기능별 전문가 에이전트 생성
    for key, selected in selected_agents.items():
        if selected and key in functional_experts:
            expert = functional_experts[key]
            agent = Agent(
                role=expert['role'],
                goal=expert['goal'],
                backstory=expert['backstory'],
                verbose=debug_mode,
                llm=llm
            )
            agents.append(agent)
            if debug_mode:
                st.write(f"✅ {expert['role']} 생성됨")

    # 최종 보고서 작성 전문가 (항상 포함)
    report_expert = Agent(
        role="전략 보고서 전문가",
        goal="종합적인 사업 전략 보고서 작성",
        backstory="전략 보고서 작성 전문가로서 복잡한 분석 결과를 명확하고 실행 가능한 전략 보고서로 변환하는 능력이 탁월합니다.",
        verbose=debug_mode,
        llm=llm
    )
    agents.append(report_expert)
    if debug_mode:
        st.write("✅ 전략 보고서 전문가 생성됨")

    return agents

# 출력 모델 정의
class MarketAnalysisOutput(BaseModel):
    market_analysis: Dict[str, Any]

class StrategyOutput(BaseModel):
    strategy: Dict[str, Any]

class FinancialPlanOutput(BaseModel):
    financial_plan: Dict[str, Any]

def get_management_theories():
    """경영 이론 목록 반환"""
    theories = {
        "일반": "일반적인 경영 전략 접근",
        "SWOT 분석": "기업의 강점, 약점, 기회, 위협 요인을 분석하여 전략 수립",
        "블루오션 전략": "경쟁이 없는 새로운 시장 창출에 초점",
        "포터의 5가지 힘": "산업 구조 분석을 통한 전략 수립",
        "핵심 역량": "기업의 핵심 능력을 기반으로 한 전략",
        "밸류 체인": "가치 사슬 분석을 통한 경쟁우위 확보",
        "개방형 혁신": "외부 자원을 활용한 혁신 전략",
        "파괴적 혁신": "시장을 근본적으로 변화시키는 혁신 전략",
        "린 생산 방식": "낭비 제거를 통한 효율성 극대화",
        "디지털 전환": "디지털 기술을 활용한 비즈니스 모델 혁신"
    }
    return theories

def create_strategy_tasks(agents, industry, target_market, goals, active_frameworks, 
                        focus_areas, specific_concerns, analysis_depth, output_focus,
                        additional_instructions, debug_mode=False):
    """전략 수립을 위한 태스크 생성"""
    tasks = []
    
    # 태스크 설명에 AI 요청사항 추가
    ai_instructions = f"""
    당신은 경영 전략 전문가로서 매우 상세하고 실용적인 전략 보고서를 작성해야 합니다.
    
    중점 분석 영역:
    {chr(10).join([f"- {area}" for area in focus_areas])}
    
    특별 고려사항:
    {specific_concerns}
    
    분석 깊이: {analysis_depth}
    
    중점 출력 항목:
    {chr(10).join([f"- {item}" for item in output_focus])}
    
    추가 지시사항:
    {additional_instructions}
    
    요구사항:
    1. 모든 분석은 구체적인 데이터와 수치를 포함해야 합니다
    2. 각 전략에 대해 상세한 실행 계획을 제시해야 합니다
    3. 산업 특성을 고려한 실질적인 제안이 필요합니다
    4. 리스크 요인과 대응 방안을 구체적으로 기술해야 합니다
    5. 재무적 관점의 분석이 포함되어야 합니다
    """

    # 시장 분석 태스크 설명 수정
    market_analysis_task = Task(
        description=f"""
        다음 산업과 목표 시장에 대한 매우 상세한 시장 분석을 수행하세요:
        
        산업: {industry}
        목표 시장: {target_market}
        사업 목표: {goals}
        
        {ai_instructions}
        
        다음 형식으로 결과를 작성하세요:
        
        # 시장 분석 보고서
        
        ## 1. 시장 개요
        ### 1.1 시장 규모 및 성장성
        - 현재 시장 규모 (구체적 수치)
        - 과거 3년간의 성장률
        - 향후 5년간 성장 전망
        - 시장 성장 동인 분석
        
        ### 1.2 시장 구조 분석
        - 시장 세그먼트별 규모와 특성
        - 유통 구조 분석
        - 수익성 구조 분석
        - 주요 성공 요인
        
        ### 1.3 시장 트렌드
        - 소비자 행동 변화
        - 기술 발전 동향
        - 규제 환경 변화
        - 글로벌 트렌드
        
        ## 2. 경쟁 환경 분석
        ### 2.1 주요 경쟁사 프로필
        - 시장 점유율
        - 핵심 역량
        - 전략적 포지션
        - 재무적 성과
        
        ### 2.2 경쟁 구도 분석
        - 경쟁 강도
        - 가격 경쟁 상황
        - 기술 경쟁 현황
        - 서비스 차별화 요소
        
        ## 3. 고객 분석
        ### 3.1 고객 세그먼테이션
        - 인구통계학적 특성
        - 행동 패턴
        - 구매 결정 요인
        - 브랜드 충성도
        
        ### 3.2 고객 니즈 분석
        - 핵심 니즈
        - 불만족 요인
        - 잠재 니즈
        - 가치 제안 기회
        
        ## 4. 외부 환경 분석
        ### 4.1 정책/규제 환경
        - 현행 규제
        - 예상되는 정책 변화
        - 규제 리스크
        - 정책적 기회
        
        ### 4.2 기술 환경
        - 핵심 기술 동향
        - 기술 발전 전망
        - 기술 도입 장벽
        - 기술 투자 필요성
        
        ## 5. 시장 기회와 위협
        ### 5.1 기회 요인
        - 시장 성장 기회
        - 경쟁 우위 확보 기회
        - 신규 시장 진입 기회
        - 기술 혁신 기회
        
        ### 5.2 위협 요인
        - 시장 리스크
        - 경쟁 위협
        - 기술적 위협
        - 규제적 위협
        
        ### 5.3 대응 전략
        - 단기 대응 방안
        - 중장기 대응 전략
        - 리스크 관리 방안
        - 모니터링 체계
        """,
        expected_output="상세한 시장 분석 보고서를 마크다운 형식으로 작성하세요.",
        agent=agents[0]
    )
    tasks.append(market_analysis_task)

    # 프레임워크별 분석 태스크 생성
    for i, framework in enumerate(active_frameworks):
        framework_task = Task(
            description=f"""
            {framework['name']}을 사용하여 다음 사업에 대한 전략 분석을 수행하세요:
            
            산업: {industry}
            목표 시장: {target_market}
            사업 목표: {goals}
            
            {ai_instructions}
            
            프레임워크 설명: {framework['description']}
            
            다음 형식으로 결과를 작성하세요:
            
            # {framework['name']} 분석 보고서
            
            ## 1. 프레임워크 적용 결과
            ### 1.1 핵심 요소 분석
            - 각 구성요소별 상세 분석
            - 요소간 상호작용 분석
            - 주요 발견사항
            
            ### 1.2 경쟁력 분석
            - 현재 경쟁력 수준
            - 잠재적 경쟁 우위
            - 개선 필요 영역
            
            ## 2. 전략적 시사점
            ### 2.1 핵심 발견사항
            - 주요 기회 영역
            - 핵심 위험 요소
            - 전략적 대응 방향
            
            ### 2.2 실행 과제
            - 단기 과제
            - 중기 과제
            - 장기 과제
            
            ## 3. 실행 전략
            ### 3.1 단기 전략 (0-6개월)
            - 즉시 실행 과제
            - 필요 자원
            - 기대 효과
            
            ### 3.2 중기 전략 (6-18개월)
            - 주요 추진 과제
            - 역량 강화 계획
            - 중간 목표
            
            ### 3.3 장기 전략 (18개월 이상)
            - 전략적 목표
            - 역량 고도화
            - 시장 포지셔닝
            
            ## 4. 기대효과
            ### 4.1 정량적 효과
            - 매출 기여도
            - 시장 점유율
            - 수익성 개선
            
            ### 4.2 정성적 효과
            - 브랜드 가치
            - 고객 만족도
            - 조직 역량
            
            ## 5. 위험요소 및 대응방안
            ### 5.1 주요 리스크
            - 내부 리스크
            - 외부 리스크
            - 실행 리스크
            
            ### 5.2 대응 전략
            - 리스크별 대응 방안
            - 모니터링 체계
            - 비상 계획
            """,
            expected_output=f"상세한 {framework['name']} 분석 보고서를 마크다운 형식으로 작성하세요.",
            agent=agents[i+1]
        )
        tasks.append(framework_task)

    # 3. 최종 전략 보고서 태스크
    final_report_task = Task(
        description=f"""
        다음 사업에 대한 종합적인 전략 보고서를 작성하세요:
        
        산업: {industry}
        목표 시장: {target_market}
        사업 목표: {goals}
        
        {ai_instructions}
        
        다음 형식으로 결과를 작성하세요:
        
        # 종합 사업 전략 보고서
        
        ## 1. Executive Summary
        ### 1.1 전략 개요
        - 핵심 전략 방향
        - 주요 목표
        - 기대 효과
        
        ### 1.2 주요 실행 과제
        - 단기 과제 (0-6개월)
        - 중기 과제 (6-18개월)
        - 장기 과제 (18개월 이상)
        
        ## 2. 시장 및 경쟁 분석
        ### 2.1 시장 현황
        - 시장 규모 및 성장성
        - 주요 트렌드
        - 기회 요인
        
        ### 2.2 경쟁 환경
        - 주요 경쟁사 분석
        - 경쟁 구도
        - 차별화 요소
        
        ## 3. 사업 전략
        ### 3.1 비즈니스 모델
        - 가치 제안
        - 수익 모델
        - 핵심 자원
        
        ### 3.2 성장 전략
        - 시장 진입 전략
        - 확장 전략
        - 파트너십 전략
        
        ## 4. 실행 계획
        ### 4.1 단계별 추진 계획
        - 1단계: 시장 진입 (0-6개월)
        - 2단계: 시장 확대 (7-18개월)
        - 3단계: 사업 고도화 (19개월 이상)
        
        ### 4.2 필요 자원
        - 인적 자원
        - 물적 자원
        - 재무 자원
        
        ### 4.3 조직 구조
        - 조직 체계
        - 역할과 책임
        - 의사결정 체계
        
        ## 5. 재무 계획
        ### 5.1 투자 계획
        - 초기 투자
        - 운영 비용
        - 추가 투자
        
        ### 5.2 수익성 분석
        - 매출 전망
        - 수익성 지표
        - 손익분기점
        
        ## 6. 리스크 관리
        ### 6.1 주요 리스크
        - 시장 리스크
        - 운영 리스크
        - 재무 리스크
        
        ### 6.2 대응 방안
        - 리스크별 대응 전략
        - 모니터링 체계
        - 비상 계획
        """,
        expected_output="상세한 종합 전략 보고서를 마크다운 형식으로 작성하세요.",
        agent=agents[-1]
    )
    tasks.append(final_report_task)

    return tasks

def analyze_strategy(agents, strategy_content):
    """전략 분석을 위한 태스크 생성"""
    tasks = []
    
    # 시장 분석 태스크
    market_analysis = Task(
        description=f"""
        다음 사업 전략을 분석하여 종합적인 평가를 제시하세요:
        
        {strategy_content}
        
        다음 형식으로 결과를 작성하세요:
        
        # 전략 분석 보고서
        
        ## 1. 시장 관점 분석
        - 시장 기회와 위험 요소
        - 경쟁 환경 평가
        - 성장 가능성 분석
        
        ## 2. 전략적 적합성
        - 전략의 실행 가능성
        - 자원 및 역량 적합성
        - 차별화 요소 평가
        
        ## 3. 재무적 타당성
        - 수익성 전망
        - 투자 대비 효과
        - 재무적 리스크
        
        ## 4. 개선 제안
        - 보완이 필요한 영역
        - 구체적 개선 방안
        - 우선순위 과제
        """,
        expected_output="상세한 전략 분석 보고서를 마크다운 형식으로 작성하세요.",
        agent=agents[0]  # 첫 번째 에이전트 사용
    )
    tasks.append(market_analysis)
    
    return tasks

def convert_crew_output_to_dict(crew_output):
    """CrewOutput 객체를 딕셔너리로 변환"""
    try:
        result = {}
        
        if crew_output and hasattr(crew_output, 'tasks_output'):
            # 각 태스크의 결과를 처리
            for task_output in crew_output.tasks_output:
                if hasattr(task_output, 'raw'):
                    # 마크다운 형식의 출력을 파싱
                    content = task_output.raw
                    
                    # 마크다운 헤더를 찾아서 섹션 분리
                    lines = content.split('\n')
                    current_section = None
                    current_content = []
                    
                    for line in lines:
                        if line.startswith('# '):
                            if current_section:
                                result[current_section] = '\n'.join(current_content)
                            current_section = line[2:].strip()
                            current_content = []
                        else:
                            current_content.append(line)
                    
                    if current_section:
                        result[current_section] = '\n'.join(current_content)
        
        return result
        
    except Exception as e:
        st.error(f"결과 변환 중 오류 발생: {str(e)}")
        return {"error": str(e)}

def get_strategies():
    """저장된 전략 목록 조회"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT strategy_id, title, industry, target_market, 
                   created_at, status, description, content
            FROM business_strategies
            ORDER BY created_at DESC
        """)
        strategies = cursor.fetchall()
        cursor.close()
        conn.close()
        return strategies
    except Exception as e:
        st.error(f"전략 조회 중 오류 발생: {str(e)}")
        return []

def get_strategy_detail(strategy_id):
    """특정 전략의 상세 내용 조회"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT *
            FROM business_strategies
            WHERE strategy_id = %s
        """, (strategy_id,))
        strategy = cursor.fetchone()
        cursor.close()
        conn.close()
        return strategy
    except Exception as e:
        st.error(f"전략 상세 조회 중 오류 발생: {str(e)}")
        return None

def format_market_analysis(data):
    """시장 분석 결과를 마크다운 형식으로 변환"""
    # 주요 정보 박스 추가
    info_box = """
    🎯 **핵심 지표**
    |지표|수치|
    |---|---|
    |시장 규모|{}|
    |연간 성장률|{}|
    |시장 점유율 목표|{}|
    |예상 손익분기점|{}|
    |초기 투자 비용|{}|
    """.format(
        data['market_size']['current'],
        data['market_size']['growth_rate'],
        data.get('target_market', {}).get('market_share_goal', 'N/A'),
        data.get('break_even', {}).get('point', 'N/A'),
        data.get('initial_investment', {}).get('total', 'N/A')
    )

    return f"""
    {info_box}

    ### 시장 규모 및 성장성
    - 현재 시장 규모: {data['market_size']['current']}
    - 연간 성장률: {data['market_size']['growth_rate']}
    - 향후 전망: {data['market_size']['forecast']}

    ### 주요 경쟁사 분석
    {chr(10).join([f'''
    #### {comp['name']}
    - 강점:
      {chr(10).join([f"  - {s}" for s in comp['strengths']])}
    - 약점:
      {chr(10).join([f"  - {w}" for w in comp['weaknesses']])}''' for comp in data['competitors']])}

    ### 목표 시장 특성
    - 주요 특성:
      {chr(10).join([f"  - {c}" for c in data['target_market']['characteristics']])}
    - 고객 니즈:
      {chr(10).join([f"  - {n}" for n in data['target_market']['needs']])}

    ### 시장 진입 분석
    - 진입 장벽:
      {chr(10).join([f"  - {b}" for b in data['entry_analysis']['barriers']])}
    """

def format_strategy(data):
    """전략 분석 결과를 마크다운 형식으로 변환"""
    # 주요 정보 박스 추가
    info_box = """
    💡 **전략 핵심 요약**
    |구분|내용|
    |---|---|
    |핵심 가치 제안|{}|
    |주요 차별화 요소|{}|
    |목표 고객층|{}|
    |핵심 성공 요인|{}|
    |우선순위 과제|{}|
    """.format(
        data['differentiation']['value_proposition'],
        ", ".join(data['differentiation']['key_points'][:2]),
        data['core_strategy'].get('target_segment', 'N/A'),
        data['core_strategy'].get('key_objectives', ['N/A'])[0],
        data['execution_plan'][0]['phase'] if data['execution_plan'] else 'N/A'
    )

    return f"""
    {info_box}

    # 🎯 사업 전략 요약

    ## 1️⃣ 전략적 방향성

    ### 비전
    > {data['core_strategy']['vision']}

    ### 미션
    > {data['core_strategy']['mission']}

    ### 핵심 목표
    {chr(10).join([f"- 🎯 {obj}" for obj in data['core_strategy']['key_objectives']])}

    ## 2️⃣ 차별화 전략

    ### 핵심 가치 제안
    > {data['differentiation']['value_proposition']}

    ### 차별화 요소
    {chr(10).join([f"- ✨ {point}" for point in data['differentiation']['key_points']])}

    ## 3️⃣ 핵심 역량 개발

    {chr(10).join([f'''
    ### {comp['area']} 💪
    - **개발 계획**
      > {comp['development_plan']}
    - **목표 시점**: `{comp['timeline']}`''' for comp in data['competencies']])}

    ## 4️⃣ 실행 로드맵

    {chr(10).join([f'''
    ### 📍 {phase['phase']} ({phase['duration']})

    **주요 활동**
    {chr(10).join([f"- ▫️ {action}" for action in phase['actions']])}

    **마일스톤**
    {chr(10).join([f"- 🏁 {milestone}" for milestone in phase['milestones']])}
    ''' for phase in data['execution_plan']])}
    """

def format_financial_plan(data):
    """재무 계획 결과를 마크다운 형식으로 변환"""
    # 주요 정보 박스 추가
    info_box = """
    💰 **재무 주요 지표**
    |지표|금액/비율|
    |---|---|
    |초기 투자비용|{}|
    |예상 연매출|{}|
    |영업이익률|{}|
    |손익분기점|{}|
    |투자회수기간|{}|
    """.format(
        data['initial_investment']['total'],
        data['profitability']['revenue_forecast'][0]['amount'],
        data['profitability']['margins']['operating'],
        data['break_even']['point'],
        data.get('roi_period', 'N/A')
    )

    return f"""
    {info_box}
    [기존 내용...]
    """

def display_strategy_content(content):
    """전략 내용을 마크다운 형식으로 표시"""
    try:
        if isinstance(content, dict):
            for section, text in content.items():
                if section != "error":  # 에러가 아닌 경우만 표시
                    st.markdown(f"# {section}")
                    st.markdown(text)
        elif isinstance(content, str):
            st.markdown(content)
        else:
            st.error("지원되지 않는 형식의 결과입니다.")
            
    except Exception as e:
        st.error(f"결과 표시 중 오류가 발생했습니다: {str(e)}")

def save_strategy_to_db(title, industry, target_market, goals, content, frameworks_used, additional_info=None):
    """전략 보고서를 DB에 저장"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor()
        
        # 전략 기본 정보 저장
        insert_query = """
        INSERT INTO business_strategies (
            title, industry, target_market, description, content, created_at
        ) VALUES (%s, %s, %s, %s, %s, NOW())
        """
        
        cursor.execute(insert_query, (
            title,
            industry,
            target_market,
            goals,
            json.dumps(content, ensure_ascii=False)
        ))
        
        conn.commit()
        return True, "전략이 성공적으로 저장되었습니다."
        
    except Exception as e:
        return False, f"전략 저장 중 오류가 발생했습니다: {str(e)}"
        
    finally:
        if conn:
            conn.close()

def main():
    st.title("사업 전략 AI 어시스턴트")
    
    # 디버그 모드 설정
    debug_mode = st.sidebar.checkbox("디버그 모드", help="에이전트와 태스크의 실행 과정을 자세히 표시합니다.")
    st.session_state.debug_mode = debug_mode

    # 전략 프레임워크 선택 섹션
    st.sidebar.header("🎯 전략 프레임워크 선택")
    frameworks = {
        "SWOT": {
            "name": "SWOT 분석",
            "description": "강점, 약점, 기회, 위협 요인 분석"
        },
        "Blue_Ocean": {
            "name": "블루오션 전략",
            "description": "가치 혁신을 통한 새로운 시장 창출"
        },
        "Porter_Five": {
            "name": "포터의 5가지 힘",
            "description": "산업 구조와 경쟁 환경 분석"
        },
        "BMC": {
            "name": "비즈니스 모델 캔버스",
            "description": "비즈니스 모델의 9가지 핵심 요소 분석"
        },
        "4P": {
            "name": "마케팅 믹스(4P)",
            "description": "제품, 가격, 유통, 촉진 전략"
        },
        "STP": {
            "name": "STP 전략",
            "description": "시장 세분화, 타겟팅, 포지셔닝"
        }
    }
    
    selected_frameworks = {}
    for key, framework in frameworks.items():
        selected_frameworks[key] = st.sidebar.checkbox(
            f"{framework['name']}", 
            help=framework['description']
        )

    # 에이전트 선택 섹션
    st.sidebar.header("🤖 전문가 에이전트 선택")
    agents_config = {
        "market_analyst": {
            "name": "시장 분석가",
            "description": "시장 동향과 경쟁 환경 분석"
        },
        "strategy_consultant": {
            "name": "전략 컨설턴트",
            "description": "전략 수립 및 실행 계획 개발"
        },
        "marketing_expert": {
            "name": "마케팅 전문가",
            "description": "마케팅 및 판매 전략 수립"
        },
        "financial_analyst": {
            "name": "재무 분석가",
            "description": "재무 계획 및 수익성 분석"
        },
        "operations_expert": {
            "name": "운영 전문가",
            "description": "운영 효율성 및 프로세스 최적화"
        },
        "risk_manager": {
            "name": "리스크 관리자",
            "description": "리스크 식별 및 대응 전략"
        }
    }

    selected_agents = {}
    for key, agent in agents_config.items():
        selected_agents[key] = st.sidebar.checkbox(
            f"{agent['name']}", 
            help=agent['description']
        )

    tab1, tab2 = st.tabs(["전략 수립", "전략 조회/분석"])
    
    with tab1:
        st.header("새로운 사업 전략 수립")
        
        # 입력 폼
        with st.form("strategy_form"):
            title = st.text_input("전략 제목")
            industry = st.text_input("산업 분야")
            target_market = st.text_input("목표 시장")
            goals = st.text_area("사업 목표")
            
            # 주요 정보 입력 섹션
            st.subheader("📌 주요 정보")
            col1, col2 = st.columns(2)
            
            with col1:
                market_size = st.text_input("시장 규모 (단위: 억원)")
                growth_rate = st.text_input("연간 성장률 (%)")
                target_share = st.text_input("목표 시장 점유율 (%)")
                
            with col2:
                competitors = st.text_area("주요 경쟁사", height=100)
                key_customers = st.text_area("핵심 고객층", height=100)
            
            # 상세 전략 정보
            st.subheader("💡 상세 전략 정보")
            col3, col4 = st.columns(2)
            
            with col3:
                value_proposition = st.text_area("핵심 가치 제안", height=100)
                competitive_advantage = st.text_area("경쟁 우위 요소", height=100)
                
            with col4:
                key_resources = st.text_area("핵심 자원/역량", height=100)
                success_factors = st.text_area("주요 성공 요인", height=100)
            
            # 실행 계획 정보
            st.subheader("⚡ 실행 계획")
            initial_investment = st.text_input("초기 투자 비용 (단위: 억원)")
            break_even = st.text_input("예상 손익분기점 시점 (개월)")
            key_milestones = st.text_area("주요 마일스톤", height=100)
            
            # AI 요청 정보 박스 추가
            st.subheader("🤖 AI 분석 요청사항")
            col5, col6 = st.columns(2)
            
            with col5:
                focus_areas = st.multiselect(
                    "중점 분석 영역",
                    ["시장 진입 전략", "경쟁 우위 확보", "수익성 개선", "리스크 관리", 
                     "마케팅 전략", "운영 효율화", "기술 혁신", "조직 구조"],
                    help="AI가 특별히 중점을 두고 분석할 영역을 선택하세요"
                )
                specific_concerns = st.text_area(
                    "특별 고려사항",
                    help="AI가 특별히 고려해야 할 사항이나 우려되는 점을 작성하세요",
                    height=100
                )
                
            with col6:
                analysis_depth = st.select_slider(
                    "분석 깊이",
                    options=["기본", "상세", "심층"],
                    value="상세",
                    help="AI 분석의 상세도를 선택하세요"
                )
                output_focus = st.multiselect(
                    "중점 출력 항목",
                    ["실행 계획", "재무 분석", "리스크 분석", "마케팅 전략", 
                     "경쟁사 분석", "기술 로드맵", "조직 설계"],
                    help="결과 보고서에서 특히 상세히 다루어야 할 항목을 선택하세요"
                )
            
            # 추가 지시사항
            additional_instructions = st.text_area(
                "AI에게 추가 지시사항",
                help="AI에게 전달할 추가적인 지시사항이나 요청사항을 자유롭게 작성하세요",
                height=100
            )
            
            # 전략 수립 시작 버튼
            submitted = st.form_submit_button("전략 수립 시작")
        
        # 폼 밖에서 전략 생성 및 저장 처리
        if submitted:
            if not all([title, industry, target_market, goals]):
                st.error("모든 필드를 입력해주세요.")
                return
            
            if not any(selected_frameworks.values()):
                st.error("최소 하나 이상의 전략 프레임워크를 선택해주세요.")
                return

            with st.spinner(f"AI 팀이 전략을 수립하고 있습니다..."):
                try:
                    # 선택된 프레임워크 정보 생성
                    active_frameworks = [
                        {"name": frameworks[k]["name"], "description": frameworks[k]["description"]}
                        for k, v in selected_frameworks.items() if v
                    ]
                    
                    if debug_mode:
                        st.write("### 🔍 선택된 프레임워크:")
                        for f in active_frameworks:
                            st.write(f"- {f['name']}")

                    # 에이전트 생성 및 태스크 실행
                    agents = create_agents(selected_agents, active_frameworks, debug_mode)
                    tasks = create_strategy_tasks(
                        agents, industry, target_market, goals, active_frameworks,
                        focus_areas, specific_concerns, analysis_depth, output_focus,
                        additional_instructions, debug_mode
                    )
                    
                    crew = Crew(
                        agents=agents,
                        tasks=tasks,
                        process=Process.sequential,
                        verbose=debug_mode
                    )
                    
                    result = crew.kickoff()
                    result_dict = convert_crew_output_to_dict(result)
                    
                    # 세션 스테이트에 모든 결과 저장
                    st.session_state.strategy_result = {
                        'title': title,
                        'industry': industry,
                        'target_market': target_market,
                        'goals': goals,
                        'content': result_dict,
                        'frameworks_used': active_frameworks,
                        'additional_info': {
                            'market_size': market_size,
                            'growth_rate': growth_rate,
                            'target_share': target_share,
                            'competitors': competitors,
                            'key_customers': key_customers,
                            'value_proposition': value_proposition,
                            'competitive_advantage': competitive_advantage,
                            'key_resources': key_resources,
                            'success_factors': success_factors,
                            'initial_investment': initial_investment,
                            'break_even': break_even,
                            'key_milestones': key_milestones
                        }
                    }
                    
                    # 결과 표시
                    st.markdown("### 📊 전략 분석 결과")
                    display_strategy_content(result_dict)
                    
                except Exception as e:
                    st.error(f"전략 수립 중 오류가 발생했습니다: {str(e)}")

    # 폼 밖에서 저장 및 다운로드 버튼 표시
    if 'strategy_result' in st.session_state:
        col1, col2 = st.columns(2)
        with col1:
            if st.button("전략 저장", key="save_strategy"):
                success, message = save_strategy_to_db(
                    st.session_state.strategy_result['title'],
                    st.session_state.strategy_result['industry'],
                    st.session_state.strategy_result['target_market'],
                    st.session_state.strategy_result['goals'],
                    st.session_state.strategy_result['content'],
                    st.session_state.strategy_result['frameworks_used'],
                    st.session_state.strategy_result['additional_info']
                )
                
                if success:
                    st.success(message)
                else:
                    st.error(message)
        
        with col2:
            # 마크다운 파일로 다운로드
            markdown_content = f"""# {st.session_state.strategy_result['title']} 전략 보고서

## 기본 정보
- 산업: {st.session_state.strategy_result['industry']}
- 목표 시장: {st.session_state.strategy_result['target_market']}
- 사업 목표: {st.session_state.strategy_result['goals']}

## 전략 분석 결과
"""
            
            # 각 섹션을 마크다운에 추가
            for section, content in st.session_state.strategy_result['content'].items():
                markdown_content += f"\n# {section}\n{content}\n"
            
            # 마크다운 파일로 다운로드
            st.download_button(
                label="전략 보고서 다운로드",
                data=markdown_content,
                file_name=f"{st.session_state.strategy_result['title']}_전략보고서.md",
                mime="text/markdown",
                key="download_strategy"  # 고유 키 추가
            )

    with tab2:
        st.header("전략 조회 및 분석")
        
        # 전략 선택 옵션
        view_option = st.radio(
            "조회 방식 선택",
            ["저장된 전략 조회", "새로운 전략 문서 분석"],
            horizontal=True
        )
        
        if view_option == "저장된 전략 조회":
            strategies = get_strategies()
            
            if strategies:
                selected_strategy = st.selectbox(
                    "조회할 전략 선택",
                    strategies,
                    format_func=lambda x: f"{x['title']} ({x['created_at'].strftime('%Y-%m-%d')})"
                )
                
                if selected_strategy:
                    st.markdown(f"## {selected_strategy['title']}")
                    
                    # 기본 정보 표시
                    st.markdown("""
                    |구분|내용|
                    |---|---|
                    |**산업 분야**|{}|
                    |**목표 시장**|{}|
                    |**작성일**|{}|
                    """.format(
                        selected_strategy['industry'],
                        selected_strategy['target_market'],
                        selected_strategy['created_at'].strftime('%Y-%m-%d')
                    ))
                    
                    # 전략 내용 표시
                    st.markdown("### 사업 목표")
                    st.markdown(selected_strategy['description'])
                    
                    # AI 분석 결과 표시
                    if selected_strategy.get('content'):
                        try:
                            content = json.loads(selected_strategy['content'])
                            st.markdown("### AI 분석 결과")
                            display_strategy_content(content)
                            
                            # 재분석 옵션
                            if st.button("전략 재분석"):
                                with st.spinner("AI 팀이 전략을 재분석하고 있습니다..."):
                                    strategy_detail = get_strategy_detail(selected_strategy['strategy_id'])
                                    if strategy_detail:
                                        # frameworks_used에서 active_frameworks 생성
                                        frameworks_used = json.loads(strategy_detail.get('frameworks_used', '[]'))
                                        
                                        # 에이전트 생성 및 태스크 실행
                                        agents = create_agents(selected_agents, frameworks_used, debug_mode)
                                        tasks = analyze_strategy(agents, strategy_detail['description'])
                                        crew = Crew(
                                            agents=agents,
                                            tasks=tasks,
                                            process=Process.sequential
                                        )
                                        result = crew.kickoff()
                                        result_dict = convert_crew_output_to_dict(result)
                                        
                                        st.markdown("### 재분석 결과")
                                        display_strategy_content(result_dict)
                        
                        except json.JSONDecodeError:
                            st.warning("AI 분석 결과를 불러오는 중 오류가 발생했습니다.")
        
        else:  # 새로운 전략 문서 분석
            uploaded_file = st.file_uploader("분석할 전략 문서 업로드", type=['txt', 'md', 'json'])
            
            if uploaded_file:
                content = uploaded_file.read().decode('utf-8')
                
                if st.button("분석 시작"):
                    with st.spinner("AI 팀이 전략을 분석하고 있습니다..."):
                        agents = create_agents(selected_agents, active_frameworks, debug_mode)
                        tasks = analyze_strategy(agents, content)
                        crew = Crew(
                            agents=agents,
                            tasks=tasks,
                            process=Process.sequential
                        )
                        result = crew.kickoff()
                        result_dict = convert_crew_output_to_dict(result)
                        
                        st.markdown("### 분석 결과")
                        display_strategy_content(result_dict)

if __name__ == "__main__":
    main() 