import streamlit as st
import mysql.connector
from datetime import datetime
import os
from dotenv import load_dotenv
from openai import OpenAI
import anthropic
import json
import base64
import requests
import graphviz
import traceback

# 환경 변수 로드
load_dotenv()

# OpenAI 클라이언트 초기화
openai = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Anthropic 클라이언트 초기화
anthropic_client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))

# 페이지 설정
st.set_page_config(page_title="의사결정 지원 시스템", page_icon="��", layout="wide")

# === MCP-STYLE MODEL SELECTION & DEFAULTS ===
OUTPUT_TOKEN_INFO = {
    "claude-3-5-sonnet-latest": {"max_tokens": 8192},
    "claude-3-5-haiku-latest": {"max_tokens": 8192},
    "claude-3-7-sonnet-latest": {"max_tokens": 16384},
    "gpt-4o": {"max_tokens": 8192},
    "gpt-4o-mini": {"max_tokens": 8192},
}

# Model selection UI (MCP style)
has_anthropic_key = os.environ.get("ANTHROPIC_API_KEY") is not None
has_openai_key = os.environ.get("OPENAI_API_KEY") is not None
available_models = []
if has_anthropic_key:
    available_models.extend([
        "claude-3-7-sonnet-latest",
        "claude-3-5-sonnet-latest",
        "claude-3-5-haiku-latest",
    ])
if has_openai_key:
    available_models.extend(["gpt-4o", "gpt-4o-mini"])
if not available_models:
    available_models = ["claude-3-7-sonnet-latest"]

if 'selected_model' not in st.session_state:
    st.session_state.selected_model = 'claude-3-7-sonnet-latest'

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

def analyze_with_ai(title, description, options, reference_files=None, model_choice="claude-3-7-sonnet-latest"):
    """AI 분석 수행"""
    try:
        base_prompt = f"""
다음 의사결정 안건을 분석해주세요:

제목: {title}
설명: {description}
"""
        if reference_files:
            base_prompt += "\n추가 참고 자료:\n"
            for file in reference_files:
                base_prompt += f"""
파일명: {file['filename']}
내용:
{file['content']}
---
"""
        base_prompt += f"""
옵션들:
{json.dumps([{
    '이름': opt['name'],
    '장점': opt['advantages'],
    '단점': opt['disadvantages'],
    '예상기간': opt['duration'],
    '우선순위': opt['priority']
} for opt in options], ensure_ascii=False, indent=2)}

다음 형식으로 분석해주세요:

1. 각 옵션별 객관적 분석
2. 각 옵션의 실현 가능성과 위험도
3. 우선순위 추천과 그 이유
4. 최종 추천안과 구체적인 실행 방안

분석시 제공된 모든 정보(설명 및 추가 참고 자료)를 종합적으로 고려해주세요.
분석은 객관적이고 전문적인 관점에서 수행해주세요."""
        # Model logic
        if model_choice.startswith("gpt-4"):
            response = openai.chat.completions.create(
                model=model_choice,
                messages=[{"role": "user", "content": base_prompt}],
                temperature=0.7,
                max_tokens=OUTPUT_TOKEN_INFO.get(model_choice, {"max_tokens": 2000})["max_tokens"]
            )
            return response.choices[0].message.content
        else:  # Claude 모델 사용
            response = anthropic_client.messages.create(
                model=model_choice,
                max_tokens=OUTPUT_TOKEN_INFO.get(model_choice, {"max_tokens": 2000})["max_tokens"],
                messages=[{"role": "user", "content": base_prompt}]
            )
            return response.content[0].text
    except Exception as e:
        st.error(f"AI 분석 중 오류 발생: {str(e)}")
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

def perform_perplexity_search(query, debug_mode=False):
    """Perplexity API를 사용한 검색 수행"""
    api_key = os.getenv('PERPLEXITY_API_KEY')
    if not api_key:
        st.error("Perplexity API 키가 설정되지 않았습니다.")
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    url = "https://api.perplexity.ai/chat/completions"
    
    data = {
        "model": "sonar",
        "messages": [
            {
                "role": "system",
                "content": "Be precise, professional, and analytical in your responses. Always include sources when available."
            },
            {
                "role": "user",
                "content": query
            }
        ]
    }
    
    if debug_mode:
        st.write("=== API 요청 디버그 정보 ===")
        st.write("URL:", url)
        st.write("Headers:", {k: v if k != 'Authorization' else f'Bearer {api_key[:8]}...' for k, v in headers.items()})
        st.write("Request Data:", json.dumps(data, indent=2, ensure_ascii=False))
    
    try:
        response = requests.post(url, headers=headers, json=data)
        
        if debug_mode:
            st.write("\n=== API 응답 디버그 정보 ===")
            st.write(f"Status Code: {response.status_code}")
            st.write("Response Headers:", dict(response.headers))
            try:
                response_data = response.json()
                st.write("Response JSON:", json.dumps(response_data, indent=2, ensure_ascii=False))
            except:
                st.write("Raw Response:", response.text)
        
        if response.status_code != 200:
            error_msg = f"API 오류 (상태 코드: {response.status_code})"
            try:
                error_data = response.json()
                if 'error' in error_data:
                    error_msg += f"\n오류 내용: {error_data['error']}"
            except:
                error_msg += f"\n응답 내용: {response.text}"
            st.error(error_msg)
            return None
        
        result = response.json()
        
        # 응답에서 텍스트와 출처 추출
        if 'choices' in result and len(result['choices']) > 0:
            content = result['choices'][0]['message']['content']
            
            # 출처 정보가 있는 경우 별도로 표시
            sources = []
            if 'sources' in result['choices'][0]['message']:
                sources = result['choices'][0]['message']['sources']
            
            # 출처 정보가 본문에 포함된 경우 (URL이나 참조 형식으로)
            source_section = "\n\n**출처:**"
            if sources:
                source_section += "\n" + "\n".join([f"- {source}" for source in sources])
            elif "[" in content and "]" in content:  # 본문에 참조 형식으로 포함된 경우
                import re
                citations = re.findall(r'\[(.*?)\]', content)
                if citations:
                    source_section += "\n" + "\n".join([f"- {citation}" for citation in citations])
            
            # URL 형식의 출처 추출
            urls = re.findall(r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s)"\']', content)
            if urls:
                if source_section == "\n\n**출처:**":
                    source_section += "\n" + "\n".join([f"- {url}" for url in urls])
            
            # 출처 정보가 있는 경우에만 추가
            if source_section != "\n\n**출처:**":
                return content + source_section
            return content
            
        return None
        
    except requests.exceptions.RequestException as e:
        st.error(f"Perplexity API 요청 실패: {str(e)}")
        if debug_mode:
            st.error(f"상세 오류: {traceback.format_exc()}")
        return None
    except Exception as e:
        st.error(f"예상치 못한 오류 발생: {str(e)}")
        if debug_mode:
            st.error(f"상세 오류: {traceback.format_exc()}")
        return None

def get_agent_tools(agent_type):
    """에이전트별 특화 도구 반환"""
    tools = {
        'financial_agent': """
재무 분석 도구:
1. ROI 계산기: 투자수익률 = (순이익 - 초기투자) / 초기투자 × 100
2. NPV 계산: 순현재가치 = Σ(미래현금흐름 / (1 + 할인율)^t)
3. 손익분기점 분석: BEP = 고정비용 / (단위당 매출 - 단위당 변동비)
4. 현금흐름 분석: 영업활동, 투자활동, 재무활동 현금흐름 구분
5. 재무비율 분석: 유동성, 수익성, 안정성 비율 계산

분석시 위 도구들을 활용하여 구체적인 수치와 함께 분석해주세요.
""",
        'legal_agent': f"""
법률 검토 도구:
1. 규제 준수성 체크리스트
   - 관련 법규 및 규제 식별
   - 인허가 요건 확인
   - 의무사항 점검
2. 계약 위험도 평가 매트릭스
3. 법적 책임 범위 분석
4. 지적재산권 검토 도구
5. 규제 변화 영향도 평가
6. 실시간 법률 검색: Perplexity API를 통한 최신 법률/규제 정보 조회

각 도구를 활용하여 법적 리스크를 구체적으로 분석해주세요.
실시간 검색 기능을 활용하여 최신 법률 및 규제 동향을 분석에 반영해주세요.
""",
        'market_agent': f"""
시장 분석 도구:
1. PEST 분석: 정치, 경제, 사회, 기술 요인 분석
2. 5-Forces 분석: 산업 내 경쟁 구조 분석
3. SWOT 분석: 강점, 약점, 기회, 위협 요인 분석
4. 시장 세분화 도구: 고객 그룹 분류 및 특성 분석
5. 경쟁사 매핑: 주요 경쟁사 포지셔닝 분석
6. TAM-SAM-SOM 분석: 시장 규모 추정
7. 실시간 시장 검색: Perplexity API를 통한 최신 시장 동향 조사

각 분석 도구를 활용하여 시장 기회와 위험을 구체적으로 평가해주세요.
실시간 검색 기능을 활용하여 최신 시장 동향을 분석에 반영해주세요.
""",
        'risk_agent': """
리스크 관리 도구:
1. 리스크 매트릭스: 발생가능성과 영향도 평가
2. 리스크 히트맵: 리스크 우선순위 시각화
3. 시나리오 분석: 최선/최악/기본 시나리오 분석
4. 민감도 분석: 주요 변수별 영향도 분석
5. 리스크 완화 전략 템플릿
6. 비상 대응 계획 수립 도구

각 도구를 활용하여 종합적인 리스크 평가와 대응 방안을 제시해주세요.
""",
        'tech_agent': """
기술 분석 도구:
1. 기술 성숙도 평가(TRL) 매트릭스
2. 기술 로드맵 작성 도구
3. 기술 격차 분석(Gap Analysis)
4. 기술 의존성 매핑
5. 구현 복잡도 평가
6. 기술 부채 분석
7. 확장성 평가 도구

각 도구를 활용하여 기술적 실현 가능성과 제약사항을 분석해주세요.
""",
        'hr_agent': """
인사/조직 분석 도구:
1. 조직 영향도 평가 매트릭스
2. 인력 수요 예측 모델
3. 스킬 갭 분석 도구
4. 조직 문화 영향도 평가
5. 변화 관리 준비도 평가
6. 교육/훈련 니즈 분석

각 도구를 활용하여 인적 자원과 조직적 측면의 영향을 분석해주세요.
""",
        'operation_agent': """
운영 분석 도구:
1. 프로세스 매핑 도구
2. 운영 효율성 평가 매트릭스
3. 자원 할당 최적화 모델
4. 병목 구간 분석
5. 품질 관리 도구
6. 운영 비용 분석
7. 생산성 측정 도구

각 도구를 활용하여 운영상의 효율성과 실행 가능성을 분석해주세요.
""",
        'strategy_agent': """
전략 분석 도구:
1. 전략적 적합성 평가 매트릭스
2. 비즈니스 모델 캔버스
3. 가치 사슬 분석
4. 포트폴리오 분석(BCG 매트릭스)
5. 시나리오 플래닝
6. 전략 실행 로드맵
7. 핵심 성공 요인(CSF) 분석

각 도구를 활용하여 전략적 타당성과 장기적 영향을 분석해주세요.
"""
    }
    return tools.get(agent_type, "")

def analyze_with_agents(title, description, options, reference_files, active_agents, debug_mode=False, model_name="claude-3-7-sonnet-latest"):
    """멀티 에이전트 분석 수행"""
    try:
        results = {}
        simplified_options = [{
            'name': opt['name'],
            'advantages': opt.get('advantages', ''),
            'disadvantages': opt.get('disadvantages', ''),
            'duration': opt['duration'],
            'priority': opt['priority']
        } for opt in options]
        for agent_type, is_active in active_agents.items():
            if not is_active or agent_type == 'integration_agent':
                continue
            if debug_mode:
                st.write(f"🤖 {agent_type} 분석 시작...")
            agent_tools = get_agent_tools(agent_type)
            additional_info = ""
            if agent_type == 'market_agent':
                market_search = perform_perplexity_search(
                    f"""다음 주제에 대한 최신 시장 동향을 분석해주세요:\n제목: {title}\n설명: {description[:200]}\n분석 관점:\n1. 시장 규모와 성장성\n2. 주요 경쟁사 현황\n3. 최근 트렌드와 변화\n4. 잠재적 기회와 위험 요소""",
                    debug_mode
                )
                if market_search:
                    additional_info = f"\n\n[실시간 시장 동향 분석]\n{market_search}"
            elif agent_type == 'legal_agent':
                legal_search = perform_perplexity_search(
                    f"""다음 주제와 관련된 법률 및 규제 사항을 검토해주세요:\n제목: {title}\n설명: {description[:200]}\n검토 관점:\n1. 관련 법규 및 규제 현황\n2. 필요한 인허가 사항\n3. 잠재적 법적 리스크\n4. 규제 준수를 위한 요구사항""",
                    debug_mode
                )
                if legal_search:
                    additional_info = f"\n\n[실시간 법률/규제 분석]\n{legal_search}"
            base_prompt = f"""
당신은 {agent_type.replace('_', ' ').title()} 입니다.
다음 의사결정 안건을 분석해주세요.

제목: {title}
설명: {description[:1000]}...

[분석 도구]
{agent_tools}

[특별 분석 지침]
이번 분석에서는 다음 사항을 특히 중점적으로 고려해주세요:
{description[1000:] if len(description) > 1000 else '일반적인 관점에서 분석해주세요.'}
{additional_info}

옵션 개요:
{json.dumps(simplified_options, ensure_ascii=False, indent=2)}

분석 결과에는 다음과 같은 형식의 flowchart를 포함해주세요:

```mermaid
graph LR
    A[주요 옵션] --> B[영향 1]
    A --> C[영향 2]
    B --> D[결과 1]
    C --> E[결과 2]
```

위 형식을 참고하여 실제 분석 내용에 맞는 flowchart를 생성해주세요.
각 노드는 명확한 설명을 포함해야 합니다.

반드시 제공된 분석 도구들을 활용하여 구체적이고 정량적인 분석을 수행해주세요.
"""
            detail_prompt = f"""
            옵션 상세:
            {json.dumps(options, ensure_ascii=False, indent=2)}
            """
            try:
                if model_name.startswith("claude"):
                    response = anthropic_client.messages.create(
                        model=model_name,
                        max_tokens=OUTPUT_TOKEN_INFO.get(model_name, {"max_tokens": 2000})["max_tokens"],
                        messages=[{
                            "role": "user",
                            "content": base_prompt
                        }]
                    )
                    analysis_content = response.content[0].text
                else:
                    response = openai.chat.completions.create(
                        model=model_name,
                        messages=[{
                            "role": "user",
                            "content": base_prompt
                        }],
                        temperature=0.7,
                        max_tokens=OUTPUT_TOKEN_INFO.get(model_name, {"max_tokens": 2000})["max_tokens"]
                    )
                    analysis_content = response.choices[0].message.content
                if model_name.startswith("claude"):
                    detail_response = anthropic_client.messages.create(
                        model=model_name,
                        max_tokens=OUTPUT_TOKEN_INFO.get(model_name, {"max_tokens": 2000})["max_tokens"],
                        messages=[{
                            "role": "user",
                            "content": detail_prompt
                        }]
                    )
                    detail_content = detail_response.content[0].text
                else:
                    detail_response = openai.chat.completions.create(
                        model=model_name,
                        messages=[{
                            "role": "user",
                            "content": detail_prompt
                        }],
                        temperature=0.7,
                        max_tokens=OUTPUT_TOKEN_INFO.get(model_name, {"max_tokens": 2000})["max_tokens"]
                    )
                    detail_content = detail_response.choices[0].message.content
                combined_analysis = f"""
                기본 분석:
                {analysis_content}

                상세 분석:
                {detail_content}
                """
                results[agent_type] = {
                    'analysis': combined_analysis,
                    'recommendations': extract_recommendations(combined_analysis),
                    'risk_assessment': extract_risk_assessment(combined_analysis)
                }
            except Exception as e:
                st.error(f"{agent_type} 분석 중 오류 발생: {str(e)}")
                if debug_mode:
                    st.write(f"오류 상세: {traceback.format_exc()}")
                results[agent_type] = {
                    'analysis': f"분석 실패: {str(e)}",
                    'recommendations': [],
                    'risk_assessment': []
                }
        if active_agents.get('integration_agent', False):
            integration_prompt = f"""
            다음은 각 전문가 에이전트의 분석 결과입니다. 이를 종합적으로 분석하여 최종 권고안을 도출해주세요:

            {json.dumps(results, ensure_ascii=False, indent=2)}

            다음 형식으로 응답해주세요:
            1. 종합 분석
            2. 최종 권고안
            3. 주요 리스크 및 대응 방안
            4. 실행 로드맵
            """
            if model_name.startswith("claude"):
                integration_response = anthropic_client.messages.create(
                    model=model_name,
                    max_tokens=OUTPUT_TOKEN_INFO.get(model_name, {"max_tokens": 2000})["max_tokens"],
                    messages=[{
                        "role": "user",
                        "content": integration_prompt
                    }]
                )
                results['integration'] = {
                    'analysis': integration_response.content[0].text,
                    'recommendations': extract_recommendations(integration_response.content[0].text),
                    'risk_assessment': extract_risk_assessment(integration_response.content[0].text)
                }
            else:
                integration_response = openai.chat.completions.create(
                    model=model_name,
                    messages=[{
                        "role": "user",
                        "content": integration_prompt
                    }],
                    temperature=0.7,
                    max_tokens=OUTPUT_TOKEN_INFO.get(model_name, {"max_tokens": 2000})["max_tokens"]
                )
                results['integration'] = {
                    'analysis': integration_response.choices[0].message.content,
                    'recommendations': extract_recommendations(integration_response.choices[0].message.content),
                    'risk_assessment': extract_risk_assessment(integration_response.choices[0].message.content)
                }
        return results
    except Exception as e:
        st.error(f"분석 중 오류 발생: {str(e)}")
        if debug_mode:
            st.write(f"오류 상세: {traceback.format_exc()}")
        return {"error": str(e)}

def delete_ai_analysis(case_id):
    """기존 AI 분석 결과 삭제"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            DELETE FROM decision_ai_analysis 
            WHERE case_id = %s
        """, (case_id,))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"AI 분석 삭제 중 오류 발생: {str(e)}")
        return False
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

def generate_recommendation(agent_type, options):
    """에이전트별 추천 의견 생성"""
    try:
        prompt = f"""
        {agent_type.replace('_', ' ').title()} 관점에서 다음 옵션들 중 
        가장 추천할 만한 옵션과 그 이유를 설명해주세요:

        옵션들:
        {json.dumps([{
            '이름': opt['name'],
            '우선순위': opt['priority'],
            '예상기간': opt['duration']
        } for opt in options], ensure_ascii=False, indent=2)}

        분석 결과를 Mermaid 차트로 표현해주세요.
        예시:
        ```mermaid
        graph TD
            A[최우선 추천] --> B[옵션명]
            B --> C[주요 이유 1]
            B --> D[주요 이유 2]
        ```
        """

        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        return response.choices[0].message.content
    except Exception as e:
        st.error(f"추천 의견 생성 중 오류 발생: {str(e)}")
        return "추천 의견을 생성할 수 없습니다."

def generate_risk_assessment(agent_type, options):
    """에이전트별 위험도 평가 생성"""
    try:
        prompt = f"""
        {agent_type.replace('_', ' ').title()} 관점에서 다음 옵션들의 
        위험 요소를 분석하고 대응 방안을 제시해주세요:

        옵션들:
        {json.dumps([{
            '이름': opt['name'],
            '우선순위': opt['priority'],
            '예상기간': opt['duration']
        } for opt in options], ensure_ascii=False, indent=2)}

        분석 결과를 Mermaid 차트로 표현해주세요.
        예시:
        ```mermaid
        graph TD
            A[위험 요소] --> B[위험 1]
            A --> C[위험 2]
            B --> D[대응 방안 1]
            C --> E[대응 방안 2]
        ```
        """

        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        return response.choices[0].message.content
    except Exception as e:
        st.error(f"위험도 평가 생성 중 오류 발생: {str(e)}")
        return "위험도 평가를 생성할 수 없습니다."

def mermaid_to_graphviz(mermaid_code):
    """Mermaid 코드를 Graphviz로 변환"""
    try:
        # Mermaid 코드에서 노드와 엣지 추출
        import re
        
        # flowchart/graph 형식 파싱
        nodes = {}
        edges = []
        
        # 노드 정의 찾기 (예: A[내용])
        node_pattern = r'([A-Za-z0-9_]+)\[(.*?)\]'
        for match in re.finditer(node_pattern, mermaid_code):
            node_id, node_label = match.groups()
            nodes[node_id] = node_label
        
        # 엣지 정의 찾기 (예: A --> B)
        edge_pattern = r'([A-Za-z0-9_]+)\s*-->\s*([A-Za-z0-9_]+)'
        edges = re.findall(edge_pattern, mermaid_code)
        
        # Graphviz 객체 생성
        dot = graphviz.Digraph()
        dot.attr(rankdir='LR')  # 왼쪽에서 오른쪽으로 방향 설정
        
        # 노드 추가
        for node_id, node_label in nodes.items():
            dot.node(node_id, node_label)
        
        # 엣지 추가
        for src, dst in edges:
            dot.edge(src, dst)
        
        return dot
    except Exception as e:
        st.error(f"차트 변환 중 오류 발생: {str(e)}")
        return None

def extract_recommendations(text):
    """텍스트에서 추천 사항 추출"""
    recommendations = []
    lines = text.split('\n')
    in_recommendations = False
    
    for line in lines:
        line = line.strip()
        # 추천 사항 섹션 시작 확인
        if '추천' in line or 'recommendation' in line.lower():
            in_recommendations = True
            continue
        # 다음 섹션 시작 확인
        if line and line.startswith('#') or line.startswith('=='):
            in_recommendations = False
        # 추천 사항 수집
        if in_recommendations and line and not line.startswith('#'):
            recommendations.append(line)
    
    # 추천 사항이 없으면 전체 텍스트 반환
    return '\n'.join(recommendations) if recommendations else text

def extract_risk_assessment(text):
    """텍스트에서 위험 평가 추출"""
    risks = []
    lines = text.split('\n')
    in_risks = False
    
    for line in lines:
        line = line.strip()
        # 위험 평가 섹션 시작 확인
        if '위험' in line or 'risk' in line.lower():
            in_risks = True
            continue
        # 다음 섹션 시작 확인
        if line and line.startswith('#') or line.startswith('=='):
            in_risks = False
        # 위험 평가 수집
        if in_risks and line and not line.startswith('#'):
            risks.append(line)
    
    # 위험 평가가 없으면 전체 텍스트 반환
    return '\n'.join(risks) if risks else text

def display_mermaid_chart(markdown_text):
    """Mermaid 차트가 포함된 마크다운 텍스트를 표시"""
    if not isinstance(markdown_text, str):
        st.warning("차트 데이터가 문자열 형식이 아닙니다.")
        return
        
    import re
    mermaid_pattern = r"```mermaid\n(.*?)\n```"
    
    # 일반 마크다운과 Mermaid 차트 분리
    parts = re.split(mermaid_pattern, markdown_text, flags=re.DOTALL)
    
    for i, part in enumerate(parts):
        if i % 2 == 0:  # 일반 마크다운
            if part.strip():
                st.markdown(part)
        else:  # Mermaid 차트
            # Graphviz로 변환하여 표시
            dot = mermaid_to_graphviz(part)
            if dot:
                st.graphviz_chart(dot)
            else:
                # 변환 실패 시 코드 표시
                st.code(part, language="mermaid")

def get_short_model_name(model_name):
    """긴 모델 이름을 짧은 버전으로 변환"""
    model_mapping = {
        "claude-3-7-sonnet-latest": "claude-3.7",
        "gpt-4o-mini": "gpt-4o-mini"
    }
    return model_mapping.get(model_name, model_name)

def main():
    st.title("🎯 의사결정 지원 시스템")
    
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
    
    # AI 에이전트 설정
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
            hr_agent = st.checkbox("인사/조직 전문가", value=True)
            
        with col3:
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

    # 모델 선택 UI (Claude 3.7 디폴트, MCP 스타일)
    st.session_state.selected_model = st.selectbox(
        "사용할 모델",
        options=available_models,
        index=available_models.index(st.session_state.selected_model) if st.session_state.selected_model in available_models else 0,
        help="분석에 사용할 AI 모델을 선택하세요 (Claude는 ANTHROPIC_API_KEY 필요, OpenAI는 OPENAI_API_KEY 필요)"
    )
    model_name = st.session_state.selected_model

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
                    with st.spinner("AI가 분석중입니다..."):
                        # 멀티 에이전트 분석 실행
                        analysis_results = analyze_with_agents(
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
                            
                            # 각 에이전트의 분석 결과 저장
                            for agent_type, analysis in analysis_results.items():
                                if isinstance(analysis, dict):
                                    save_ai_analysis(
                                        st.session_state.current_case_id,
                                        f"AI {agent_type} ({get_short_model_name(model_name)})",
                                        analysis.get('analysis', ''),
                                        analysis.get('recommendations', ''),
                                        analysis.get('risk_assessment', '')
                                    )
                                else:
                                    # 문자열인 경우 전체를 분석 내용으로 처리
                                    save_ai_analysis(
                                        st.session_state.current_case_id,
                                        f"AI {agent_type} ({get_short_model_name(model_name)})",
                                        str(analysis),
                                        extract_recommendations(str(analysis)),
                                        extract_risk_assessment(str(analysis))
                                    )
        
        # AI 분석 결과 표시 - 에이전트별 탭으로 구성
        if st.session_state.ai_analysis_results:
            st.write("### AI 분석 결과")
            
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
                    display_mermaid_chart(analysis['analysis'])
                    
                    st.markdown("#### 추천 의견")
                    display_mermaid_chart(analysis['recommendations'])
                    
                    st.markdown("#### 위험도 평가")
                    display_mermaid_chart(analysis['risk_assessment'])

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
                    
                    # 분석 결과 저장 설정을 위한 체크박스
                    save_to_db = st.checkbox(
                        "재분석 결과를 DB에 자동 저장",
                        value=False,
                        key=f"save_to_db_{case['case_id']}",
                        help="체크하면 재분석 시 결과가 자동으로 DB에 저장됩니다."
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
                            
                            analysis_results = analyze_with_agents(
                                case['title'],
                                modified_description,
                                formatted_options,
                                reference_files,
                                active_agents,
                                debug_mode,
                                model_name
                            )
                            
                            if analysis_results:
                                # DB 저장이 선택된 경우 자동 저장 수행
                                if save_to_db:
                                    with st.spinner("분석 결과를 DB에 저장중..."):
                                        # 기존 분석 결과 삭제
                                        delete_ai_analysis(case['case_id'])
                                        st.info("기존 분석 결과를 삭제하고 새로운 분석을 저장합니다...")
                                        
                                        for agent_type, analysis in analysis_results.items():
                                            try:
                                                if isinstance(analysis, dict):
                                                    success = save_ai_analysis(
                                                        case['case_id'],
                                                        f"AI {agent_type} ({get_short_model_name(model_name)}) - {additional_instructions[:30]}...",
                                                        analysis.get('analysis', ''),
                                                        analysis.get('recommendations', ''),
                                                        analysis.get('risk_assessment', '')
                                                    )
                                                else:
                                                    success = save_ai_analysis(
                                                        case['case_id'],
                                                        f"AI {agent_type} ({get_short_model_name(model_name)}) - {additional_instructions[:30]}...",
                                                        str(analysis),
                                                        extract_recommendations(str(analysis)),
                                                        extract_risk_assessment(str(analysis))
                                                    )
                                                
                                                if success:
                                                    st.success(f"✅ {agent_type} 분석 결과가 저장되었습니다.")
                                                else:
                                                    st.error(f"❌ {agent_type} 분석 결과 저장에 실패했습니다.")
                                            except Exception as e:
                                                st.error(f"❌ {agent_type} 분석 결과 저장 중 오류 발생: {str(e)}")
                                        
                                        st.success("✅ 모든 AI 분석이 DB에 저장되었습니다!")
                                else:
                                    st.info("💡 분석 결과가 화면에만 표시됩니다. DB에는 저장되지 않습니다.")
                                
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
                                        display_mermaid_chart(analysis['analysis'])
                                        
                                        st.markdown("#### 추천 의견")
                                        display_mermaid_chart(analysis['recommendations'])
                                        
                                        st.markdown("#### 위험도 평가")
                                        display_mermaid_chart(analysis['risk_assessment'])
                                
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
                    
                    **예상 기간:** {opt['estimated_duration']}""")
                    
                    if opt.get('additional_info'):
                        st.markdown("**추가 정보:**")
                        st.markdown(opt['additional_info'])
                    
                    st.markdown("---")
                
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
                            display_mermaid_chart(analysis['analysis_content'])
                            
                            # 안전하게 recommendations 키 확인
                            if isinstance(analysis, dict) and analysis.get('recommendations'):
                                st.markdown("**추천 의견:**")
                                display_mermaid_chart(analysis['recommendations'])
                            
                            # 안전하게 risk_assessment 키 확인
                            if isinstance(analysis, dict) and analysis.get('risk_assessment'):
                                st.markdown("**위험도 평가:**")
                                display_mermaid_chart(analysis['risk_assessment'])
                
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