import streamlit as st
import pandas as pd
from datetime import datetime
import mysql.connector
import os
from dotenv import load_dotenv
import json
from openai import OpenAI
import graphviz

# .env 파일 로드
load_dotenv()

# OpenAI 클라이언트 초기화
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# 페이지 설정
st.set_page_config(page_title="TOC 분석 시스템", page_icon="🔄", layout="wide")

# TOC 모델 정의
TOC_MODELS = {
    "5단계 집중 프로세스": {
        "steps": [
            "제약 식별(Identify): 시스템의 성과를 제한하는 제약 찾기",
            "제약 활용(Exploit): 기존 제약을 최대한 활용",
            "다른 요소 종속(Subordinate): 모든 활동을 제약에 동기화",
            "제약 격상(Elevate): 제약 해소를 위한 투자/개선",
            "재평가(Return): 새로운 제약 발견 시 프로세스 반복"
        ],
        "questions": [
            "1. 식별 단계: 현재 시스템에서 가장 큰 제약(병목)은 무엇입니까? 어떤 증거로 이를 확인할 수 있습니까?",
            "2. 활용 단계: 현재의 제약 요소를 최대한 활용하기 위해 어떤 즉각적인 개선이 가능합니까?",
            "3. 종속 단계: 다른 모든 프로세스와 자원을 제약에 맞추려면 어떻게 조정해야 합니까?",
            "4. 격상 단계: 제약을 근본적으로 해소하기 위해 어떤 투자나 변화가 필요합니까?",
            "5. 재평가 단계: 이전 단계들의 개선 후 새로운 제약은 무엇이 될 것으로 예상됩니까?"
        ],
        "description": "시스템의 제약을 찾아 개선하는 기본적인 TOC 적용 모델"
    },
    "사고 프로세스": {
        "tools": [
            "현상 구조도(CRT): 바람직하지 않은 현상들의 인과관계 분석",
            "충돌 해소도(EC): 근본 갈등의 전제를 찾아 해결책 도출",
            "미래 구조도(FRT): 제안된 해결책의 효과와 부작용 검증",
            "전제 조건도(PRT): 해결책 실행을 위한 중간 목표 설정",
            "전환 계획도(TT): 구체적인 실행 계획 수립"
        ],
        "tool_descriptions": {
            "CRT": """
### 현상 구조도(Current Reality Tree)
- **목적**: 현재 시스템의 바람직하지 않은 현상들(UDE)과 그 원인들 간의 인과관계를 파악
- **주요 특징**:
  - 현재 상황의 논리적 분석
  - 핵심 문제(Core Problem)의 식별
  - 문제들 간의 인과관계 시각화
- **사용 시점**: 문제의 근본 원인을 찾고자 할 때
- **기대 효과**: 표면적 증상이 아닌 근본 원인에 대한 해결책 도출 가능
            """,
            "EC": """
### 충돌 해소도(Evaporating Cloud)
- **목적**: 시스템 내의 근본적인 갈등 상황을 파악하고 해결책 도출
- **주요 특징**:
  - 갈등 상황의 양면성 분석
  - 전제 조건의 타당성 검토
  - 창의적 해결책 도출
- **사용 시점**: 서로 상충되는 요구사항이나 목표가 있을 때
- **기대 효과**: 양측 모두가 수용할 수 있는 win-win 해결책 도출
            """,
            "FRT": """
### 미래 구조도(Future Reality Tree)
- **목적**: 제안된 해결책이 의도한 효과를 가져올 것인지 검증
- **주요 특징**:
  - 해결책 실행의 파급 효과 예측
  - 부작용 식별 및 대응 방안 수립
  - 긍정적 효과의 강화 방안 모색
- **사용 시점**: 해결책 실행 전 효과성 검증이 필요할 때
- **기대 효과**: 해결책의 실효성 검증 및 부작용 최소화
            """,
            "PRT": """
### 전제 조건도(Prerequisite Tree)
- **목적**: 목표 달성을 위한 중간 단계와 장애물 식별
- **주요 특징**:
  - 장애물 식별 및 분석
  - 중간 목표 설정
  - 단계별 달성 전략 수립
- **사용 시점**: 해결책 실행의 구체적 단계가 필요할 때
- **기대 효과**: 실행 가능한 단계별 계획 수립
            """,
            "TT": """
### 전환 계획도(Transition Tree)
- **목적**: 현재 상태에서 목표 상태로의 구체적인 실행 계획 수립
- **주요 특징**:
  - 단계별 실행 계획
  - 마일스톤 설정
  - 진행 상황 모니터링 포인트 정의
- **사용 시점**: 구체적인 실행 계획이 필요할 때
- **기대 효과**: 체계적이고 실행 가능한 변화 관리 계획 수립
            """
        },
        "questions": [
            "현재 상황에서 발생하는 바람직하지 않은 현상들은 무엇입니까? (각 현상을 구체적으로 기술해주세요)",
            "이러한 현상들 사이의 인과관계는 어떻게 됩니까? (A 때문에 B가 발생하는 식으로 설명해주세요)",
            "핵심적인 갈등 상황은 무엇이며, 이를 해결하기 위한 전제 조건은 무엇입니까?",
            "제안된 해결책이 실행되면 어떤 긍정적/부정적 효과가 예상됩니까?",
            "해결책 실행을 위한 구체적인 단계와 일정은 어떻게 됩니까?"
        ],
        "chart_templates": {
            "CRT": """```mermaid
graph TD
    UDE1[바람직하지 않은 현상 1] --> Effect1[영향 1]
    UDE2[바람직하지 않은 현상 2] --> Effect1
    Effect1 --> CoreProblem[핵심 문제]
    UDE3[바람직하지 않은 현상 3] --> Effect2[영향 2]
    Effect2 --> CoreProblem
```""",
            "EC": """```mermaid
graph TD
    Conflict[갈등 상황] --> Want1[원하는 것 1]
    Conflict --> Want2[원하는 것 2]
    Want1 --> Prerequisite1[전제 조건 1]
    Want2 --> Prerequisite2[전제 조건 2]
    Prerequisite1 --> Solution[해결책]
    Prerequisite2 --> Solution
```""",
            "FRT": """```mermaid
graph TD
    Action[제안된 해결책] --> Effect1[긍정적 효과 1]
    Action --> Effect2[긍정적 효과 2]
    Effect1 --> Result1[기대 결과 1]
    Effect2 --> Result2[기대 결과 2]
    Action --> Risk[잠재적 위험]
```""",
            "PRT": """```mermaid
graph LR
    Current[현재 상태] --> Obstacle1[장애물 1]
    Current --> Obstacle2[장애물 2]
    Obstacle1 --> Action1[중간 목표 1]
    Obstacle2 --> Action2[중간 목표 2]
    Action1 --> Goal[최종 목표]
    Action2 --> Goal
```""",
            "TT": """```mermaid
graph LR
    Start[시작] --> Phase1[단계 1]
    Phase1 --> Phase2[단계 2]
    Phase2 --> Phase3[단계 3]
    Phase3 --> End[완료]
    Phase1 --> Milestone1[마일스톤 1]
    Phase2 --> Milestone2[마일스톤 2]
    Phase3 --> Milestone3[마일스톤 3]
```"""
        },
        "description": "문제 해결과 변화 관리를 위한 로직 기반 도구"
    },
    "쓰루풋 회계": {
        "metrics": [
            "쓰루풋(T): 판매를 통해 생성된 돈 (매출 - 완전 변동비)",
            "재고/투자(I): 제품 생산을 위해 투자한 돈",
            "운영비용(OE): 시스템 운영에 소요되는 고정비"
        ],
        "kpis": [
            "순이익(NP) = T - OE: 실제 수익성",
            "투자수익률(ROI) = (T - OE) / I: 투자 효율성",
            "생산성(P) = T / OE: 운영 효율성",
            "회전율(IT) = T / I: 투자 회전율"
        ],
        "questions": [
            "현재 쓰루풋을 제한하는 요소는 무엇입니까?",
            "운영비용 중 불필요한 항목은 무엇입니까?",
            "재고/투자를 어떻게 최적화할 수 있습니까?",
            "각 제품/서비스의 쓰루풋 기여도는 어떠합니까?"
        ],
        "description": "제약 이론에 맞춘 회계 접근법"
    },
    "드럼-버퍼-로프": {
        "components": [
            "드럼(Drum): 제약 자원의 생산 일정",
            "버퍼(Buffer): 제약 자원 보호를 위한 시간/재고",
            "로프(Rope): 자재 투입 시점 통제 메커니즘"
        ],
        "questions": [
            "시스템의 제약 자원(드럼)은 무엇입니까?",
            "제약 자원의 최적 생산 일정은 무엇입니까?",
            "어느 정도의 보호 버퍼가 필요합니까?",
            "자재 투입은 어떻게 통제되어야 합니까?"
        ],
        "description": "생산 일정과 재고 관리를 위한 모델"
    },
    "버퍼 관리": {
        "buffers": [
            "프로젝트 버퍼: 전체 프로젝트 완료 보호",
            "피딩 버퍼: 주요 경로 합류 지점 보호",
            "자원 버퍼: 핵심 자원 가용성 보호"
        ],
        "monitoring": [
            "녹색 (0-33%): 정상 진행",
            "노란색 (34-67%): 주의 필요",
            "빨간색 (68-100%): 즉각 조치 필요"
        ],
        "questions": [
            "각 버퍼의 현재 소진율은 얼마입니까?",
            "버퍼 침범의 주요 원인은 무엇입니까?",
            "어떤 선제적 조치가 가능합니까?",
            "버퍼 크기는 적절합니까?"
        ],
        "description": "프로젝트와 생산 공정의 모니터링 및 통제"
    },
    "중요 체인 프로젝트 관리": {
        "principles": [
            "중요 체인: 자원 제약을 고려한 최장 경로",
            "안전 시간 집중화: 개별 작업의 안전여유를 프로젝트 끝으로 이동",
            "학생 증후군 제거: 마지막 순간까지 미루는 행동 방지",
            "멀티태스킹 감소: 작업 전환에 따른 낭비 제거"
        ],
        "questions": [
            "자원 제약을 고려한 중요 체인은 무엇입니까?",
            "각 작업의 현실적인 소요 시간은 얼마입니까?",
            "어떤 작업들이 병렬 처리되고 있습니까?",
            "프로젝트 버퍼는 얼마나 필요합니까?"
        ],
        "description": "프로젝트 관리를 위한 TOC 적용"
    }
}

# TOC 모델 간 연관성 정의
TOC_MODEL_RELATIONSHIPS = {
    "5단계 집중 프로세스": {
        "related_models": {
            "사고 프로세스": "제약 식별 단계에서 CRT를 활용하여 제약 분석",
            "쓰루풋 회계": "제약 활용 단계에서 쓰루풋 분석으로 최적화",
            "드럼-버퍼-로프": "제약 활용과 종속 단계에서 생산 일정 최적화",
            "버퍼 관리": "제약 활용 단계에서 버퍼 관리로 제약 보호",
            "중요 체인 프로젝트 관리": "제약 격상 단계에서 프로젝트 관리 방법론 활용"
        },
        "flow_chart": """```mermaid
graph TD
    A[제약 식별] --> B[제약 활용]
    B --> C[다른 요소 종속]
    C --> D[제약 격상]
    D --> E[재평가]
    A -.-> F[사고 프로세스/CRT]
    B -.-> G[쓰루풋 회계]
    B -.-> H[드럼-버퍼-로프]
    B -.-> I[버퍼 관리]
    D -.-> J[중요 체인]
```"""
    },
    "사고 프로세스": {
        "related_models": {
            "5단계 집중 프로세스": "CRT로 제약 식별, FRT로 해결책 검증",
            "쓰루풋 회계": "EC와 FRT에서 재무적 영향 분석",
            "드럼-버퍼-로프": "PRT와 TT에서 실행 계획 수립",
            "버퍼 관리": "FRT와 PRT에서 버퍼 설계",
            "중요 체인 프로젝트 관리": "TT를 프로젝트 계획에 활용"
        },
        "flow_chart": """```mermaid
graph TD
    A[CRT] --> B[EC]
    B --> C[FRT]
    C --> D[PRT]
    D --> E[TT]
    A -.-> F[5단계 프로세스]
    C -.-> G[쓰루풋 회계]
    E -.-> H[드럼-버퍼-로프]
    D -.-> I[버퍼 관리]
    E -.-> J[중요 체인]
```"""
    },
    "쓰루풋 회계": {
        "related_models": {
            "5단계 집중 프로세스": "제약 활용 단계의 재무적 분석",
            "사고 프로세스": "EC와 FRT에서 재무적 의사결정",
            "드럼-버퍼-로프": "생산 일정과 재고 관리의 재무적 영향",
            "버퍼 관리": "버퍼 크기 결정의 재무적 영향",
            "중요 체인 프로젝트 관리": "프로젝트 투자 결정"
        },
        "flow_chart": """```mermaid
graph TD
    A[쓰루풋] --> B[재고/투자]
    B --> C[운영비용]
    A -.-> D[5단계 프로세스]
    A -.-> E[사고 프로세스]
    B -.-> F[드럼-버퍼-로프]
    C -.-> G[버퍼 관리]
    B -.-> H[중요 체인]
```"""
    }
}

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

def get_ai_analysis(content, model_type):
    """AI를 사용한 TOC 분석 및 제안"""
    try:
        # 모델별 분석 프레임워크 정의
        analysis_frameworks = {
            "5단계 집중 프로세스": """
                제약이론의 5단계 집중 프로세스에 따라 다음 분석을 수행해주세요:

                1. 제약 식별 (Identify)
                - 현재 성과 지표 분석: {data[current_situation]}
                - 주요 제약 요인: {data[q1]}
                - 제약이 시스템에 미치는 영향

                2. 제약 활용 (Exploit)
                - 현재 제약 활용도: {data[q2]}
                - 제약 활용 최적화 방안
                - 즉시 실행 가능한 개선책

                3. 다른 요소 종속 (Subordinate)
                - 제약과 다른 요소들의 관계: {data[q3]}
                - 동기화 전략
                - 예상되는 마찰과 해결방안

                4. 제약 향상 (Elevate)
                - 제약 해소를 위한 투자/개선 계획: {data[q4]}
                - 비용-편익 분석
                - 실행 우선순위

                5. 반복 (Repeat)
                - 새로운 제약 예측: {data[q5]}
                - 모니터링 계획
                - 지속적 개선 방안

                결론 및 실행 계획:
                1. 핵심 발견사항
                2. 우선순위별 실행 항목
                3. 기대효과
                4. 위험 요소 및 대응 방안
                """,
            
            "사고 프로세스": """
                제약이론의 사고 프로세스 도구를 사용하여 다음 분석을 수행해주세요:

                1. 현상 구조도 (CRT) 분석
                - 현재 상황의 바람직하지 않은 현상들: {data[q1]}
                - 핵심 문제와 원인-결과 관계
                - 근본 원인 식별

                2. 충돌 해소도 (EC) 분석
                - 핵심 갈등 상황: {data[q2]}
                - 갈등의 전제 조건
                - 창의적 해결 방안

                3. 미래 구조도 (FRT) 검증
                - 제안된 해결책: {data[q3]}
                - 예상되는 긍정적 효과
                - 잠재적 부작용 및 대응 방안

                4. 전제 조건도 (PRT) 수립
                - 목표 달성을 위한 중간 목표: {data[q4]}
                - 장애물 식별
                - 극복 전략

                5. 전환 계획도 (TT) 작성
                - 구체적 실행 계획: {data[q5]}
                - 단계별 이행 전략
                - 모니터링 방안

                종합 권고사항:
                1. 주요 발견사항
                2. 단계별 실행 계획
                3. 성공 기준
                4. 리스크 관리 방안
                """,
            
            "쓰루풋 회계": """
                제약이론의 쓰루풋 회계 관점에서 다음 분석을 수행해주세요:

                1. 현재 재무 상태 분석
                - 쓰루풋(T): {data[쓰루풋(T)]}
                - 재고/투자(I): {data[재고/투자(I)]}
                - 운영비용(OE): {data[운영비용(OE)]}

                2. 핵심 성과 지표 분석
                - 순이익(NP) = T - OE
                - 투자수익률(ROI) = (T - OE) / I
                - 생산성(P) = T / OE
                - 회전율(IT) = T / I

                3. 개선 기회 분석
                - 쓰루풋 증대 방안: {data[q1]}
                - 운영비용 최적화: {data[q2]}
                - 재고/투자 효율화: {data[q3]}

                4. 제품/서비스 포트폴리오 분석
                - 쓰루풋 기여도: {data[q4]}
                - 제품/서비스별 우선순위
                - 자원 할당 전략

                개선 권고사항:
                1. 단기 개선 과제
                2. 중장기 개선 과제
                3. 예상 재무 효과
                4. 실행 로드맵
                """,
            
            "드럼-버퍼-로프": """
                드럼-버퍼-로프 시스템 관점에서 다음 분석을 수행해주세요:

                1. 드럼(제약 자원) 분석
                - 제약 자원 식별: {data[q1]}
                - 현재 활용도
                - 최적 생산 일정: {data[q2]}

                2. 버퍼 관리
                - 필요 버퍼 크기: {data[q3]}
                - 버퍼 위치
                - 버퍼 모니터링 방안

                3. 로프 시스템
                - 자재 투입 통제: {data[q4]}
                - 동기화 메커니즘
                - 커뮤니케이션 체계

                4. 시스템 통합
                - 전체 프로세스 조정
                - 예상 문제점
                - 대응 방안

                실행 권고사항:
                1. 구현 단계
                2. 필요 자원
                3. 예상 효과
                4. 모니터링 계획
                """,
            
            "버퍼 관리": """
                버퍼 관리 시스템 관점에서 다음 분석을 수행해주세요:

                1. 버퍼 상태 평가
                - 현재 소진율: {data[q1]}
                - 문제 영역: {data[q2]}
                - 트렌드 분석

                2. 원인 분석
                - 버퍼 침범 원인: {data[q3]}
                - 시스템적 문제
                - 특이 상황

                3. 대응 전략
                - 즉각 대응 필요 사항
                - 선제적 조치: {data[q4]}
                - 버퍼 크기 조정

                4. 모니터링 체계
                - 핵심 지표
                - 보고 체계
                - 의사결정 프로세스

                개선 권고사항:
                1. 긴급 조치 사항
                2. 중기 개선 과제
                3. 모니터링 강화 방안
                4. 리스크 관리 전략
                """,
            
            "중요 체인 프로젝트 관리": """
                중요 체인 프로젝트 관리 관점에서 다음 분석을 수행해주세요:

                1. 중요 체인 분석
                - 자원 제약 고려: {data[q1]}
                - 작업 의존성
                - 중요 경로 식별

                2. 일정 평가
                - 작업 소요 시간: {data[q2]}
                - 안전 여유 분석
                - 일정 리스크

                3. 자원 관리
                - 병렬 작업: {data[q3]}
                - 자원 충돌
                - 멀티태스킹 영향

                4. 버퍼 관리
                - 프로젝트 버퍼: {data[q4]}
                - 피딩 버퍼
                - 자원 버퍼

                실행 권고사항:
                1. 일정 최적화 방안
                2. 자원 운영 전략
                3. 리스크 관리 계획
                4. 모니터링 체계
                """
        }

        # 선택된 모델의 분석 프레임워크 가져오기
        framework = analysis_frameworks.get(model_type, "")
        
        # 분석 프레임워크에 데이터 적용
        prompt = framework.format(
            data=content['data'],
            title=content['title'],
            area=content['area']
        )

        # GPT-4에 분석 요청
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": """당신은 TOC(제약이론) 전문가입니다. 
                주어진 프레임워크에 따라 체계적이고 실용적인 분석과 권고사항을 제시해주세요.
                분석은 구체적이고 실행 가능해야 하며, 정량적 지표와 정성적 평가를 모두 포함해야 합니다."""},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2500
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"AI 분석 중 오류 발생: {str(e)}"

def save_toc_analysis(title, area, model_type, analysis_data, ai_analysis):
    """TOC 분석 저장"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor()
        
        # analysis_data에 AI 분석 결과 추가
        analysis_data['ai_analysis'] = ai_analysis
        
        cursor.execute('''
            INSERT INTO toc_analysis (
                analysis_name, analysis_type, description, analysis_data, created_by, created_at
            ) VALUES (
                %s, %s, %s, %s, %s, NOW()
            )
        ''', (
            title,
            model_type,
            analysis_data.get('current_situation', ''),
            json.dumps(analysis_data),
            'system'
        ))
        
        analysis_id = cursor.lastrowid
        conn.commit()
        cursor.close()
        conn.close()
        return True, analysis_id
    except mysql.connector.Error as err:
        st.error(f"데이터 저장 중 오류 발생: {err}")
        return False, None

def get_filtered_analyses(search_name, search_type, start_date, end_date):
    """필터링된 TOC 분석 목록 조회"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)
        
        # 기본 쿼리 작성
        query = """
            SELECT 
                analysis_id,
                analysis_name,
                analysis_type,
                description,
                analysis_data,
                created_by,
                created_at
            FROM toc_analysis
            WHERE 1=1
        """
        params = []
        
        # 검색 조건 추가
        if search_name and search_name.strip():
            query += " AND analysis_name LIKE %s"
            params.append(f"%{search_name.strip()}%")
        
        if search_type and search_type != "전체":
            query += " AND analysis_type = %s"
            params.append(search_type)
        
        if start_date:
            query += " AND DATE(created_at) >= %s"
            params.append(start_date)
        
        if end_date:
            query += " AND DATE(created_at) <= %s"
            params.append(end_date)
        
        # 정렬 조건 추가
        query += " ORDER BY created_at DESC"
        
        # 쿼리 실행 및 결과 반환
        cursor.execute(query, params)
        analyses = cursor.fetchall()
        
        # 결과가 없을 경우 디버깅을 위한 로그
        if not analyses:
            st.write("실행된 쿼리:", query)
            st.write("파라미터:", params)
            
        return analyses
        
    except mysql.connector.Error as err:
        st.error(f"데이터베이스 조회 중 오류 발생: {err}")
        return []
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_toc_analyses():
    """저장된 TOC 분석 목록 조회"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)
        
        query = """
        SELECT 
            analysis_id, 
            analysis_name,
            analysis_type,
            analysis_data,
            created_at 
        FROM toc_analysis 
        ORDER BY created_at DESC
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        # JSON 파싱 및 모델 타입 추출
        for result in results:
            if result['analysis_data']:
                analysis_data = json.loads(result['analysis_data'])
                result['model_type'] = result['analysis_type']
            
        return results
        
    except Exception as e:
        st.error(f"조회 중 오류가 발생했습니다: {str(e)}")
        return []
    finally:
        if 'conn' in locals():
            conn.close()

def get_toc_analysis_detail(analysis_id):
    """특정 TOC 분석의 상세 정보 조회"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)
        
        query = """
        SELECT * FROM toc_analysis WHERE analysis_id = %s
        """
        
        cursor.execute(query, (analysis_id,))
        return cursor.fetchone()
        
    except Exception as e:
        st.error(f"조회 중 오류가 발생했습니다: {str(e)}")
        return None
    finally:
        if 'conn' in locals():
            conn.close()

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

def display_mermaid_chart(markdown_text):
    """Mermaid 차트가 포함된 마크다운 텍스트를 표시"""
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

def get_model_analysis_form(selected_model):
    """선택된 모델에 따른 분석 폼 생성"""
    analysis_data = {}
    
    with st.form("toc_analysis_form"):
        title = st.text_input("분석 제목")
        area = st.selectbox(
            "적용 영역",
            ["마케팅", "세일즈", "운영", "생산", "물류", "재고관리", "프로젝트 관리"]
        )
        
        st.markdown("### 현재 상황 분석")
        analysis_data["current_situation"] = st.text_area(
            "현재 상황을 상세히 설명해주세요",
            help="현재 직면한 문제나 개선이 필요한 상황을 설명하세요"
        )
        
        # 모델별 질문 표시
        st.markdown(f"### {selected_model} 분석")
        
        # 사고 프로세스 모델인 경우 차트 템플릿 표시
        if selected_model == "사고 프로세스":
            st.markdown("### TOC 사고 프로세스 도구")
            for tool_name, template in TOC_MODELS[selected_model]["chart_templates"].items():
                with st.expander(f"{tool_name} - {TOC_MODELS[selected_model]['tools'][list(TOC_MODELS[selected_model]['chart_templates'].keys()).index(tool_name)]}"):
                    # 도구 설명 표시
                    st.markdown(TOC_MODELS[selected_model]["tool_descriptions"][tool_name])
                    st.markdown("#### 차트 템플릿")
                    display_mermaid_chart(template)
                    st.markdown("이 템플릿을 참고하여 아래 질문들에 답변해주세요.")
                    st.markdown("---")
        
        for i, question in enumerate(TOC_MODELS[selected_model]["questions"], 1):
            analysis_data[f"q{i}"] = st.text_area(
                f"Q{i}. {question}",
                help="가능한 한 구체적으로 답변해주세요"
            )
        
        # 모델별 추가 입력 필드
        if selected_model == "쓰루풋 회계":
            st.markdown("### 재무 지표 입력")
            for metric in TOC_MODELS[selected_model]["metrics"]:
                key = metric.split(":")[0]
                analysis_data[key] = st.number_input(
                    metric,
                    min_value=0.0,
                    format="%f"
                )
        
        elif selected_model == "버퍼 관리":
            st.markdown("### 버퍼 상태 모니터링")
            for buffer in TOC_MODELS[selected_model]["buffers"]:
                name = buffer.split(":")[0]
                status = st.selectbox(
                    f"{name} 상태",
                    ["녹색 (0-33%)", "노란색 (34-67%)", "빨간색 (68-100%)"],
                    key=f"buffer_{name}"
                )
                analysis_data[f"status_{name}"] = status
                if status != "녹색 (0-33%)":
                    analysis_data[f"action_{name}"] = st.text_area(
                        f"{name}에 대한 대응 계획",
                        help="현재 상태를 개선하기 위한 구체적인 조치 사항"
                    )
        
        # AI 분석 수행 버튼
        if st.form_submit_button("AI 분석 수행"):
            if title and area and all(v != "" for v in analysis_data.values()):
                with st.spinner("AI가 분석 중입니다..."):
                    # AI 프롬프트 개선
                    analysis = get_ai_analysis(
                        content={
                            "title": title,
                            "area": area,
                            "model": selected_model,
                            "data": analysis_data
                        },
                        model_type=selected_model
                    )
                    
                    if save_toc_analysis(title, area, selected_model, analysis_data, analysis):
                        st.session_state.ai_analysis = analysis
                        st.session_state.analysis_data = analysis_data
                        st.success("분석이 완료되고 저장되었습니다!")
                        st.session_state.active_tab = 2
                        st.rerun()
            else:
                st.error("모든 필드를 입력해주세요.")

def show_analysis_results():
    """분석 결과 표시"""
    st.markdown("## 📊 분석 결과")
    
    # 검색 필터 섹션
    with st.expander("🔍 분석 결과 검색", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            search_name = st.text_input("분석 이름으로 검색", placeholder="분석 이름 입력...")
            analysis_types = ["전체"] + list(TOC_MODELS.keys())
            search_type = st.selectbox("분석 유형", analysis_types)
        
        with col2:
            start_date = st.date_input("시작 날짜", value=None)
            end_date = st.date_input("종료 날짜", value=None)
    
    # 검색 버튼
    if st.button("🔍 검색", type="primary"):
        analyses = get_filtered_analyses(search_name, search_type, start_date, end_date)
    else:
        analyses = get_filtered_analyses(None, None, None, None)  # 초기 로드시 모든 결과 표시
    
    if not analyses:
        st.info("검색 결과가 없습니다.")
        return
    
    # 날짜별로 분석 결과 그룹화
    analyses_by_date = {}
    for analysis in analyses:
        date = analysis['created_at'].date()
        if date not in analyses_by_date:
            analyses_by_date[date] = []
        analyses_by_date[date].append(analysis)
    
    # 날짜별로 정렬된 결과 표시
    for date in sorted(analyses_by_date.keys(), reverse=True):
        st.markdown(f"### 📅 {date.strftime('%Y-%m-%d')} 분석 결과")
        for analysis in analyses_by_date[date]:
            with st.container():
                # 제목과 기본 정보
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"#### {analysis['analysis_name']}")
                    st.markdown(f"**분석 유형:** {analysis['analysis_type']}")
                    if analysis.get('description'):
                        st.markdown(f"**설명:** {analysis['description']}")
                
                with col2:
                    st.markdown(f"**생성 시각:** {analysis['created_at'].strftime('%H:%M:%S')}")
                    if analysis.get('created_by'):
                        st.markdown(f"**작성자:** {analysis['created_by']}")
                
                # 분석 데이터 표시
                if analysis.get('analysis_data'):
                    try:
                        data = json.loads(analysis['analysis_data'])
                        st.markdown("##### 상세 분석 데이터")
                        
                        # 현재 상황
                        if data.get('current_situation'):
                            st.markdown("**현재 상황:**")
                            st.markdown(data['current_situation'])
                        
                        # 영역 정보
                        if data.get('area'):
                            st.markdown(f"**영역:** {data['area']}")
                        
                        # 질문과 답변
                        for i in range(1, 6):  # 최대 5개의 질문 처리
                            q_key = f'q{i}'
                            if q_key in data:
                                st.markdown(f"**질문 {i}:**")
                                st.markdown(data[q_key])
                        
                        # AI 분석 결과
                        if data.get('ai_analysis'):
                            st.markdown("**AI 분석 결과:**")
                            st.markdown(data['ai_analysis'])
                            
                    except json.JSONDecodeError:
                        st.error("분석 데이터 형식이 올바르지 않습니다.")
                
                st.divider()

def display_analysis_data(data):
    """분석 데이터 표시"""
    if isinstance(data, dict):
        # 현재 상황
        if data.get('current_situation'):
            st.markdown("**현재 상황:**")
            st.markdown(data['current_situation'])
        
        # 영역 정보
        if data.get('area'):
            st.markdown(f"**영역:** {data['area']}")
        
        # 질문과 답변
        for i in range(1, 6):  # 최대 5개의 질문 처리
            q_key = f'q{i}'
            if q_key in data:
                st.markdown(f"**질문 {i}:**")
                st.markdown(data[q_key])
        
        # AI 분석 결과
        if data.get('ai_analysis'):
            st.markdown("**AI 분석 결과:**")
            st.markdown(data['ai_analysis'])

def create_toc_relationship_tables():
    """TOC 모델 간 연관성을 위한 테이블 생성"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        # TOC 분석 결과 간 연관성 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS toc_analysis_relationships (
                relationship_id INT AUTO_INCREMENT PRIMARY KEY,
                source_analysis_id INT,
                target_analysis_id INT,
                relationship_type VARCHAR(50),
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_analysis_id) REFERENCES toc_analysis(analysis_id),
                FOREIGN KEY (target_analysis_id) REFERENCES toc_analysis(analysis_id)
            )
        """)
        
        # TOC 모델 간 연관성 메타데이터 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS toc_model_relationships (
                model_relationship_id INT AUTO_INCREMENT PRIMARY KEY,
                source_model VARCHAR(50),
                target_model VARCHAR(50),
                relationship_type VARCHAR(50),
                description TEXT,
                flow_chart TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"테이블 생성 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def save_toc_relationship(source_id, target_id, relationship_type, description):
    """TOC 분석 결과 간 연관성 저장"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO toc_analysis_relationships 
            (source_analysis_id, target_analysis_id, relationship_type, description)
            VALUES (%s, %s, %s, %s)
        """, (source_id, target_id, relationship_type, description))
        
        conn.commit()
        return True
    except Exception as e:
        st.error(f"연관성 저장 중 오류 발생: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_related_analyses(analysis_id):
    """특정 분석과 연관된 다른 분석 결과 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT r.*, 
                   a1.title as source_title, 
                   a2.title as target_title,
                   a1.model_type as source_model,
                   a2.model_type as target_model
            FROM toc_analysis_relationships r
            JOIN toc_analysis a1 ON r.source_analysis_id = a1.analysis_id
            JOIN toc_analysis a2 ON r.target_analysis_id = a2.analysis_id
            WHERE r.source_analysis_id = %s OR r.target_analysis_id = %s
        """, (analysis_id, analysis_id))
        
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def show_model_relationships():
    """TOC 모델 간 연관성 시각화"""
    st.markdown("## TOC 모델 간 연관성")
    
    # 모델 선택
    selected_model = st.selectbox(
        "기준 모델 선택",
        list(TOC_MODEL_RELATIONSHIPS.keys())
    )
    
    if selected_model:
        # 선택된 모델의 연관성 정보 표시
        st.markdown(f"### {selected_model}의 연관 모델")
        
        # 연관성 차트 표시
        st.markdown("#### 모델 연관성 차트")
        display_mermaid_chart(TOC_MODEL_RELATIONSHIPS[selected_model]["flow_chart"])
        
        # 연관 모델 설명
        st.markdown("#### 연관 모델 설명")
        for related_model, description in TOC_MODEL_RELATIONSHIPS[selected_model]["related_models"].items():
            with st.expander(f"{related_model}와의 연관성"):
                st.write(description)

def main():
    st.title("🔄 제약이론(TOC) 분석 시스템")
    
    # 테이블 생성
    create_toc_relationship_tables()
    
    # 초기 탭 상태 설정
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = 0  # 첫 번째 탭을 기본값으로
    
    # 탭 생성
    tab1, tab2, tab3, tab4 = st.tabs([
        "TOC 모델 선택", 
        "분석 수행", 
        "결과 조회",
        "모델 연관성"  # 새로운 탭 추가
    ])
    
    with tab1:
        st.header("TOC 모델 선택")
        selected_model = st.selectbox(
            "분석에 사용할 TOC 모델을 선택하세요",
            list(TOC_MODELS.keys())
        )
        
        if selected_model:
            # 선택된 모델을 세션 상태에 저장
            st.session_state.selected_model = selected_model
            
            st.subheader(f"{selected_model} 모델 개요")
            st.write(TOC_MODELS[selected_model]["description"])
            
            # 모델별 상세 정보 표시
            if "steps" in TOC_MODELS[selected_model]:
                st.write("#### 단계:")
                for step in TOC_MODELS[selected_model]["steps"]:
                    st.write(f"- {step}")
            elif "tools" in TOC_MODELS[selected_model]:
                st.write("#### 도구:")
                for tool in TOC_MODELS[selected_model]["tools"]:
                    st.write(f"- {tool}")
            elif "metrics" in TOC_MODELS[selected_model]:
                st.write("#### 지표:")
                for metric in TOC_MODELS[selected_model]["metrics"]:
                    st.write(f"- {metric}")
            elif "components" in TOC_MODELS[selected_model]:
                st.write("#### 구성요소:")
                for component in TOC_MODELS[selected_model]["components"]:
                    st.write(f"- {component}")
            elif "buffers" in TOC_MODELS[selected_model]:
                st.write("#### 버퍼:")
                for buffer in TOC_MODELS[selected_model]["buffers"]:
                    st.write(f"- {buffer}")
            elif "principles" in TOC_MODELS[selected_model]:
                st.write("#### 원칙:")
                for principle in TOC_MODELS[selected_model]["principles"]:
                    st.write(f"- {principle}")
            
            # 분석 시작 버튼 추가
            if st.button("이 모델로 분석 시작", use_container_width=True):
                st.session_state.active_tab = 1  # 두 번째 탭으로 전환
                st.rerun()
    
    with tab2:
        if st.session_state.active_tab == 1:  # 두 번째 탭이 활성화된 경우
            st.header("TOC 분석 수행")
            if 'selected_model' in st.session_state:
                st.info(f"선택된 모델: {st.session_state.selected_model}")
                get_model_analysis_form(st.session_state.selected_model)
            else:
                st.info("먼저 'TOC 모델 선택' 탭에서 모델을 선택해주세요.")
    
    with tab3:
        show_analysis_results()
    
    with tab4:
        show_model_relationships()
    
    # 현재 활성 탭에 따라 JavaScript로 탭 전환
    if st.session_state.active_tab > 0:
        js = f"""
        <script>
            var tabs = window.parent.document.getElementsByClassName("stTabs");
            if (tabs.length > 0) {{
                tabs[0].children[{st.session_state.active_tab}].click();
            }}
        </script>
        """
        st.markdown(js, unsafe_allow_html=True)

if __name__ == "__main__":
    main() 