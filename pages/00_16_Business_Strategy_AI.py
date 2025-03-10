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
def create_agents():
    # OpenAI 모델 설정
    llm = ChatOpenAI(
        api_key=os.getenv('OPENAI_API_KEY'),
        model=os.getenv('MODEL_NAME', 'gpt-4o-mini')
    )

    # 시장 분석가 에이전트
    market_analyst = Agent(
        role='시장 분석가',
        goal='시장 동향과 경쟁 환경을 분석하여 실행 가능한 통찰을 제공',
        backstory="""당신은 20년 경력의 시장 분석 전문가입니다. 
        산업 동향을 정확히 파악하고 경쟁사 분석을 통해 
        실질적인 시장 기회를 발견하는 것이 특기입니다.""",
        llm=llm
    )

    # 전략 컨설턴트 에이전트
    strategist = Agent(
        role='전략 컨설턴트',
        goal='비즈니스 전략 수립 및 실행 계획 개발',
        backstory="""당신은 글로벌 컨설팅 펌에서 15년간 전략 컨설팅을 해온 전문가입니다.
        복잡한 비즈니스 문제를 체계적으로 분석하고 실행 가능한 해결책을 제시하는 것이 특기입니다.""",
        llm=llm
    )

    # 재무 분석가 에이전트
    financial_analyst = Agent(
        role='재무 분석가',
        goal='재무적 실행 가능성 분석 및 투자 계획 수립',
        backstory="""당신은 투자 은행과 벤처 캐피탈에서 12년간 일한 재무 전문가입니다.
        사업의 수익성과 재무적 리스크를 정확히 분석하고 현실적인 재무 계획을 수립하는 것이 특기입니다.""",
        llm=llm
    )

    return market_analyst, strategist, financial_analyst

# 출력 모델 정의
class MarketAnalysisOutput(BaseModel):
    market_analysis: Dict[str, Any]

class StrategyOutput(BaseModel):
    strategy: Dict[str, Any]

class FinancialPlanOutput(BaseModel):
    financial_plan: Dict[str, Any]

def create_strategy_tasks(agents, industry, target_market, goals):
    market_analyst, strategist, financial_analyst = agents
    
    # 시장 분석 태스크
    market_analysis = Task(
        description=f"""
        당신은 시장 분석가로서 {industry} 산업에 대한 포괄적인 시장 분석을 수행해야 합니다.
        
        분석 대상:
        - 산업: {industry}
        - 목표 시장: {target_market}
        
        다음 항목들을 상세히 분석하여 JSON 형식으로 응답해주세요:
        1. 시장 규모와 성장성
        2. 주요 경쟁사 분석 (최소 3개 기업)
        3. 목표 시장의 특성과 요구사항
        4. 시장 진입 장벽과 기회 요인

        응답은 반드시 다음과 같은 JSON 형식으로 작성해주세요:
        {{
            "market_size": {{
                "current": "현재 시장 규모",
                "growth_rate": "연간 성장률",
                "forecast": "향후 전망"
            }},
            "competitors": [
                {{
                    "name": "경쟁사명",
                    "strengths": ["강점1", "강점2"],
                    "weaknesses": ["약점1", "약점2"]
                }}
            ],
            "target_market": {{
                "characteristics": ["특성1", "특성2"],
                "needs": ["니즈1", "니즈2"]
            }},
            "entry_analysis": {{
                "barriers": ["장벽1", "장벽2"],
                "opportunities": ["기회1", "기회2"]
            }}
        }}
        """,
        expected_output="JSON formatted market analysis",
        agent=market_analyst
    )

    # 전략 수립 태스크
    strategy_development = Task(
        description=f"""
        당신은 전략 컨설턴트로서 시장 분석 결과를 바탕으로 구체적인 사업 전략을 수립해야 합니다.
        
        고려사항:
        - 사업 목표: {goals}
        - 산업: {industry}
        - 목표 시장: {target_market}
        
        다음 항목들을 포함하여 JSON 형식으로 응답해주세요:
        1. 핵심 사업 전략
        2. 차별화 전략
        3. 핵심 경쟁력 확보 방안
        4. 단계별 실행 계획

        응답은 반드시 다음과 같은 JSON 형식으로 작성해주세요:
        {{
            "core_strategy": {{
                "vision": "비전 statement",
                "mission": "미션 statement",
                "key_objectives": ["목표1", "목표2"]
            }},
            "differentiation": {{
                "value_proposition": "핵심 가치 제안",
                "key_points": ["차별화 요소1", "차별화 요소2"]
            }},
            "competencies": [
                {{
                    "area": "경쟁력 영역",
                    "development_plan": "확보 방안",
                    "timeline": "구현 시기"
                }}
            ],
            "execution_plan": [
                {{
                    "phase": "단계명",
                    "duration": "기간",
                    "actions": ["실행항목1", "실행항목2"],
                    "milestones": ["마일스톤1", "마일스톤2"]
                }}
            ]
        }}
        """,
        expected_output="JSON formatted strategy plan",
        agent=strategist
    )

    # 재무 계획 태스크
    financial_planning = Task(
        description=f"""
        당신은 재무 분석가로서 수립된 전략의 재무적 실행 가능성을 분석하고 투자 계획을 수립해야 합니다.
        
        다음 항목들을 상세히 분석하여 JSON 형식으로 응답해주세요:
        1. 초기 투자 비용 추정
        2. 예상 수익성 분석
        3. 손익분기점 분석
        4. 자금 조달 방안

        응답은 반드시 다음과 같은 JSON 형식으로 작성해주세요:
        {{
            "initial_investment": {{
                "total": "총 투자금액",
                "breakdown": [
                    {{
                        "category": "항목명",
                        "amount": "금액",
                        "description": "설명"
                    }}
                ]
            }},
            "profitability": {{
                "revenue_forecast": [
                    {{
                        "year": "연도",
                        "amount": "예상 매출",
                        "growth": "성장률"
                    }}
                ],
                "margins": {{
                    "gross": "매출총이익률",
                    "operating": "영업이익률",
                    "net": "순이익률"
                }}
            }},
            "break_even": {{
                "point": "손익분기점",
                "expected_date": "달성 예상 시기",
                "monthly_target": "월 목표 매출"
            }},
            "funding": {{
                "required_amount": "필요 자금",
                "sources": ["자금원1", "자금원2"],
                "schedule": "조달 계획"
            }}
        }}
        """,
        expected_output="JSON formatted financial plan",
        agent=financial_analyst
    )

    return [market_analysis, strategy_development, financial_planning]

def analyze_strategy(agents, strategy_content):
    market_analyst, strategist, financial_analyst = agents
    
    # 시장 분석 태스크
    market_analysis = Task(
        description=f"""
        다음 사업 전략을 시장 관점에서 분석하세요:
        
        {strategy_content}
        
        다음 항목들을 상세히 분석하여 JSON 형식으로 응답해주세요:
        1. 시장 규모와 성장성
        2. 주요 경쟁사 분석
        3. 목표 시장의 특성과 요구사항
        4. 시장 진입 장벽과 기회 요인

        응답은 반드시 다음과 같은 JSON 형식으로 작성해주세요:
        {{
            "market_size": {{
                "current": "현재 시장 규모",
                "growth_rate": "연간 성장률",
                "forecast": "향후 전망"
            }},
            "competitors": [
                {{
                    "name": "경쟁사명",
                    "strengths": ["강점1", "강점2"],
                    "weaknesses": ["약점1", "약점2"]
                }}
            ],
            "target_market": {{
                "characteristics": ["특성1", "특성2"],
                "needs": ["니즈1", "니즈2"]
            }},
            "entry_analysis": {{
                "barriers": ["장벽1", "장벽2"],
                "opportunities": ["기회1", "기회2"]
            }}
        }}
        """,
        expected_output="JSON formatted market analysis",
        agent=market_analyst
    )

    # 전략 평가 태스크
    strategy_evaluation = Task(
        description=f"""
        다음 사업 전략을 전략적 관점에서 평가하세요:
        
        {strategy_content}
        
        다음 항목들을 포함하여 JSON 형식으로 응답해주세요:
        1. 전략의 적절성
        2. 실행 가능성
        3. 차별화 요소
        4. 단계별 실행 계획

        응답은 반드시 다음과 같은 JSON 형식으로 작성해주세요:
        {{
            "core_strategy": {{
                "vision": "비전 statement",
                "mission": "미션 statement",
                "key_objectives": ["목표1", "목표2"]
            }},
            "differentiation": {{
                "value_proposition": "핵심 가치 제안",
                "key_points": ["차별화 요소1", "차별화 요소2"]
            }},
            "competencies": [
                {{
                    "area": "경쟁력 영역",
                    "development_plan": "확보 방안",
                    "timeline": "구현 시기"
                }}
            ],
            "execution_plan": [
                {{
                    "phase": "단계명",
                    "duration": "기간",
                    "actions": ["실행항목1", "실행항목2"],
                    "milestones": ["마일스톤1", "마일스톤2"]
                }}
            ]
        }}
        """,
        expected_output="JSON formatted strategy evaluation",
        agent=strategist
    )

    # 재무 평가 태스크
    financial_evaluation = Task(
        description=f"""
        다음 사업 전략을 재무적 관점에서 평가하세요:
        
        {strategy_content}
        
        다음 항목들을 상세히 분석하여 JSON 형식으로 응답해주세요:
        1. 초기 투자 비용 추정
        2. 예상 수익성 분석
        3. 손익분기점 분석
        4. 자금 조달 방안

        응답은 반드시 다음과 같은 JSON 형식으로 작성해주세요:
        {{
            "initial_investment": {{
                "total": "총 투자금액",
                "breakdown": [
                    {{
                        "category": "항목명",
                        "amount": "금액",
                        "description": "설명"
                    }}
                ]
            }},
            "profitability": {{
                "revenue_forecast": [
                    {{
                        "year": "연도",
                        "amount": "예상 매출",
                        "growth": "성장률"
                    }}
                ],
                "margins": {{
                    "gross": "매출총이익률",
                    "operating": "영업이익률",
                    "net": "순이익률"
                }}
            }},
            "break_even": {{
                "point": "손익분기점",
                "expected_date": "달성 예상 시기",
                "monthly_target": "월 목표 매출"
            }},
            "funding": {{
                "required_amount": "필요 자금",
                "sources": ["자금원1", "자금원2"],
                "schedule": "조달 계획"
            }}
        }}
        """,
        expected_output="JSON formatted financial evaluation",
        agent=financial_analyst
    )
    
    return [market_analysis, strategy_evaluation, financial_evaluation]

def convert_crew_output_to_dict(crew_output):
    """CrewOutput 객체를 딕셔너리로 변환"""
    try:
        result = {
            'raw_output': '',
            'sections': {
                'market_analysis': '',
                'strategy': '',
                'financial_plan': ''
            }
        }
        
        if crew_output and hasattr(crew_output, 'tasks_output'):
            # 각 태스크의 결과를 처리
            for i, task_output in enumerate(crew_output.tasks_output):
                if hasattr(task_output, 'raw'):
                    # JSON 문자열에서 실제 JSON 부분만 추출
                    raw_text = task_output.raw
                    if raw_text.startswith('```json'):
                        raw_text = raw_text.split('```json')[1]
                    if raw_text.endswith('```'):
                        raw_text = raw_text.rsplit('```', 1)[0]
                    
                    # 섹션에 결과 저장
                    if i == 0:
                        result['sections']['market_analysis'] = raw_text.strip()
                    elif i == 1:
                        result['sections']['strategy'] = raw_text.strip()
                    elif i == 2:
                        result['sections']['financial_plan'] = raw_text.strip()
            
            # 전체 결과 결합
            result['raw_output'] = "\n\n=== 시장 분석 ===\n" + \
                                 result['sections']['market_analysis'] + \
                                 "\n\n=== 사업 전략 ===\n" + \
                                 result['sections']['strategy'] + \
                                 "\n\n=== 재무 계획 ===\n" + \
                                 result['sections']['financial_plan']
        
        return result
        
    except Exception as e:
        st.error(f"결과 변환 중 오류 발생: {str(e)}")
        return {
            'raw_output': f"결과 처리 중 오류가 발생했습니다: {str(e)}",
            'sections': {
                'market_analysis': '',
                'strategy': '',
                'financial_plan': ''
            }
        }

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
    return f"""
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
- 기회 요인:
  {chr(10).join([f"  - {o}" for o in data['entry_analysis']['opportunities']])}
"""

def format_strategy(data):
    """전략 결과를 마크다운 형식으로 변환"""
    return f"""
### 핵심 전략
- **비전**: {data['core_strategy']['vision']}
- **미션**: {data['core_strategy']['mission']}
- **핵심 목표**:
  {chr(10).join([f"  - {obj}" for obj in data['core_strategy']['key_objectives']])}

### 차별화 전략
- **가치 제안**: {data['differentiation']['value_proposition']}
- **핵심 차별화 포인트**:
  {chr(10).join([f"  - {p}" for p in data['differentiation']['key_points']])}

### 핵심 경쟁력
{chr(10).join([f'''
#### {comp['area']}
- 개발 계획: {comp['development_plan']}
- 구현 시기: {comp['timeline']}''' for comp in data['competencies']])}

### 실행 계획
{chr(10).join([f'''
#### {phase['phase']} ({phase['duration']})
- 실행 항목:
  {chr(10).join([f"  - {a}" for a in phase['actions']])}
- 주요 마일스톤:
  {chr(10).join([f"  - {m}" for m in phase['milestones']])}''' for phase in data['execution_plan']])}
"""

def format_financial_plan(data):
    """재무 계획 결과를 마크다운 형식으로 변환"""
    return f"""
### 초기 투자 계획
- **총 투자금액**: {data['initial_investment']['total']}
- **투자 항목 상세**:
{chr(10).join([f'''  - {item['category']}: {item['amount']}
    - {item['description']}''' for item in data['initial_investment']['breakdown']])}

### 수익성 분석
#### 매출 전망
{chr(10).join([f"- {forecast['year']}: {forecast['amount']} (성장률: {forecast['growth']})" for forecast in data['profitability']['revenue_forecast']])}

#### 수익률
- 매출총이익률: {data['profitability']['margins']['gross']}
- 영업이익률: {data['profitability']['margins']['operating']}
- 순이익률: {data['profitability']['margins']['net']}

### 손익분기점 분석
- 손익분기점: {data['break_even']['point']}
- 예상 달성 시기: {data['break_even']['expected_date']}
- 월 목표 매출: {data['break_even']['monthly_target']}

### 자금 조달 계획
- 필요 자금: {data['funding']['required_amount']}
- 자금 조달원:
  {chr(10).join([f"  - {s}" for s in data['funding']['sources']])}
- 조달 일정: {data['funding']['schedule']}
"""

def display_strategy_content(content):
    """전략 내용을 마크다운 형식으로 표시"""
    try:
        if 'sections' in content:
            sections = content['sections']
            
            # 시장 분석 결과
            if sections.get('market_analysis'):
                st.markdown("## 시장 분석")
                try:
                    market_data = json.loads(sections['market_analysis'])
                    st.markdown(format_market_analysis(market_data))
                except:
                    st.markdown(sections['market_analysis'])
            
            # 전략 결과
            if sections.get('strategy'):
                st.markdown("## 사업 전략")
                try:
                    strategy_data = json.loads(sections['strategy'])
                    st.markdown(format_strategy(strategy_data))
                except:
                    st.markdown(sections['strategy'])
            
            # 재무 계획 결과
            if sections.get('financial_plan'):
                st.markdown("## 재무 계획")
                try:
                    financial_data = json.loads(sections['financial_plan'])
                    st.markdown(format_financial_plan(financial_data))
                except:
                    st.markdown(sections['financial_plan'])
    except Exception as e:
        st.error(f"결과 표시 중 오류가 발생했습니다: {str(e)}")

def main():
    st.title("사업 전략 AI 어시스턴트")
    
    tab1, tab2 = st.tabs(["전략 수립", "전략 조회/분석"])
    
    with tab1:
        st.header("새로운 사업 전략 수립")
        
        # 입력 폼
        with st.form("strategy_form"):
            title = st.text_input("전략 제목")
            industry = st.text_input("산업 분야")
            target_market = st.text_input("목표 시장")
            goals = st.text_area("사업 목표")
            
            submitted = st.form_submit_button("전략 수립 시작")
            
            if submitted:
                if not all([title, industry, target_market, goals]):
                    st.error("모든 필드를 입력해주세요.")
                    return
                
                with st.spinner("AI 팀이 전략을 수립하고 있습니다..."):
                    try:
                        # 에이전트 생성 및 실행
                        agents = create_agents()
                        tasks = create_strategy_tasks(agents, industry, target_market, goals)
                        crew = Crew(
                            agents=agents,
                            tasks=tasks,
                            process=Process.sequential
                        )
                        
                        result = crew.kickoff()
                        result_dict = convert_crew_output_to_dict(result)
                        
                        # 결과 저장
                        try:
                            conn = connect_to_db()
                            cursor = conn.cursor()
                            
                            cursor.execute("""
                                INSERT INTO business_strategies 
                                (title, industry, target_market, description, content, status)
                                VALUES (%s, %s, %s, %s, %s, 'completed')
                            """, (title, industry, target_market, goals, 
                                 json.dumps(result_dict, ensure_ascii=False)))
                            
                            conn.commit()
                            st.success("전략이 성공적으로 수립되었습니다!")
                            
                            # 전체 결과 표시
                            st.subheader("AI 팀의 분석 결과")
                            if result_dict['raw_output']:
                                sections = result_dict['sections']
                                
                                # 시장 분석 결과
                                st.markdown("## 시장 분석")
                                if sections['market_analysis']:
                                    try:
                                        market_data = json.loads(sections['market_analysis'])
                                        st.markdown(format_market_analysis(market_data))
                                    except:
                                        st.markdown(sections['market_analysis'])
                                
                                # 전략 결과
                                st.markdown("## 사업 전략")
                                if sections['strategy']:
                                    try:
                                        strategy_data = json.loads(sections['strategy'])
                                        st.markdown(format_strategy(strategy_data))
                                    except:
                                        st.markdown(sections['strategy'])
                                
                                # 재무 계획 결과
                                st.markdown("## 재무 계획")
                                if sections['financial_plan']:
                                    try:
                                        financial_data = json.loads(sections['financial_plan'])
                                        st.markdown(format_financial_plan(financial_data))
                                    except:
                                        st.markdown(sections['financial_plan'])
                            else:
                                st.warning("분석 결과가 비어있습니다.")
                        
                        except Exception as e:
                            st.error(f"저장 중 오류가 발생했습니다: {str(e)}")
                        finally:
                            if conn.is_connected():
                                cursor.close()
                                conn.close()
                    except Exception as e:
                        st.error(f"전략 수립 중 오류가 발생했습니다: {str(e)}")
    
    with tab2:
        st.header("전략 조회 및 분석")
        
        # 저장된 전략 목록 조회
        strategies = get_strategies()
        
        if strategies:
            # 전략 선택 옵션
            view_option = st.radio(
                "조회 방식 선택",
                ["저장된 전략 조회", "새로운 전략 문서 분석"],
                horizontal=True
            )
            
            if view_option == "저장된 전략 조회":
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
                            
                        except json.JSONDecodeError:
                            st.warning("AI 분석 결과를 불러오는 중 오류가 발생했습니다.")
                    
                    # 재분석 옵션
                    if st.button("전략 재분석"):
                        with st.spinner("AI 팀이 전략을 재분석하고 있습니다..."):
                            strategy_detail = get_strategy_detail(selected_strategy['strategy_id'])
                            if strategy_detail:
                                agents = create_agents()
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
            
            else:  # 새로운 전략 문서 분석
                uploaded_file = st.file_uploader("분석할 전략 문서 업로드", type=['txt', 'md', 'json'])
                
                if uploaded_file:
                    content = uploaded_file.read().decode('utf-8')
                    
                    if st.button("분석 시작"):
                        with st.spinner("AI 팀이 전략을 분석하고 있습니다..."):
                            agents = create_agents()
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
        
        else:
            st.info("저장된 전략이 없습니다. '전략 수립' 탭에서 새로운 전략을 작성해주세요.")

if __name__ == "__main__":
    main() 