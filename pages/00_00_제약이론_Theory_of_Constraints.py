import streamlit as st
import pandas as pd
from datetime import datetime
import mysql.connector
import os
from dotenv import load_dotenv
import json
from openai import OpenAI

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
            "제약 향상(Elevate): 제약 해소를 위한 투자/개선",
            "반복(Repeat): 새로운 제약 발견 시 프로세스 반복"
        ],
        "questions": [
            "현재 시스템의 주요 성과 지표는 무엇입니까?",
            "어떤 요소가 성과 향상을 가로막고 있습니까?",
            "제약 요소의 현재 활용도는 어떠합니까?",
            "제약에 맞춰 다른 요소들을 어떻게 조정할 수 있습니까?",
            "제약 해소를 위해 어떤 투자나 개선이 필요합니까?"
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
        "questions": [
            "어떤 바람직하지 않은 현상들이 있습니까?",
            "이러한 현상들 사이의 인과관계는 무엇입니까?",
            "핵심적인 갈등 상황은 무엇입니까?",
            "갈등 해결을 위한 전제 조건은 무엇입니까?",
            "해결책 실행의 장애물은 무엇입니까?"
        ],
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
    """TOC 분석 결과를 DB에 저장"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor()
        
        insert_query = """
        INSERT INTO toc_analysis (
            title, area, current_state, constraints, implementation_plan, solutions, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """
        
        # 현재 상태에 모델 타입과 입력 데이터 포함
        current_state = {
            "model_type": model_type,
            "input_data": analysis_data
        }
        
        # 제약사항은 빈 객체로 초기화
        constraints = {}
        
        # 실행 계획은 빈 객체로 초기화
        implementation_plan = {}
        
        # AI 분석 결과를 solutions에 저장
        solutions = {
            "ai_analysis": ai_analysis
        }
        
        cursor.execute(insert_query, (
            title,
            area,
            json.dumps(current_state, ensure_ascii=False),
            json.dumps(constraints, ensure_ascii=False),
            json.dumps(implementation_plan, ensure_ascii=False),
            json.dumps(solutions, ensure_ascii=False)
        ))
        
        conn.commit()
        return True
        
    except Exception as e:
        st.error(f"저장 중 오류가 발생했습니다: {str(e)}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

def get_toc_analyses():
    """저장된 TOC 분석 목록 조회"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)
        
        query = """
        SELECT 
            analysis_id, 
            title, 
            area, 
            current_state,
            created_at 
        FROM toc_analysis 
        ORDER BY created_at DESC
        """
        
        cursor.execute(query)
        results = cursor.fetchall()
        
        # JSON 파싱 및 모델 타입 추출
        for result in results:
            current_state = json.loads(result['current_state'])
            result['model_type'] = current_state.get('model_type', '알 수 없음')
            
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
    st.header("분석 결과 조회")
    
    # 검색 필터
    col1, col2, col3 = st.columns(3)
    with col1:
        search_title = st.text_input("제목 검색", "")
    with col2:
        search_area = st.selectbox(
            "영역 선택",
            ["전체"] + ["마케팅", "세일즈", "운영", "생산", "물류", "재고관리", "프로젝트 관리"]
        )
    with col3:
        search_model = st.selectbox(
            "모델 선택",
            ["전체"] + list(TOC_MODELS.keys())
        )
    
    # 최근 분석 결과 표시 (접을 수 있는 섹션으로)
    if 'ai_analysis' in st.session_state:
        with st.expander("최근 분석 결과 보기", expanded=True):
            st.info(f"모델: {st.session_state.selected_model}")
            st.markdown("### 입력 데이터")
            st.json(st.session_state.analysis_data)
            st.markdown("### AI 분석 결과")
            st.write(st.session_state.ai_analysis)
            st.markdown("---")
    
    # 과거 분석 결과 목록
    st.subheader("과거 분석 결과")
    
    # 검색 쿼리 수정
    def get_filtered_analyses(title="", area="전체", model="전체"):
        try:
            conn = connect_to_db()
            cursor = conn.cursor(dictionary=True)
            
            conditions = []
            params = []
            
            if title:
                conditions.append("title LIKE %s")
                params.append(f"%{title}%")
            
            if area != "전체":
                conditions.append("area = %s")
                params.append(area)
            
            query = """
            SELECT 
                analysis_id, 
                title, 
                area, 
                current_state,
                created_at 
            FROM toc_analysis
            """
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            
            query += " ORDER BY created_at DESC"
            
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            # JSON 파싱 및 모델 타입 추출
            filtered_results = []
            for result in results:
                current_state = json.loads(result['current_state'])
                result['model_type'] = current_state.get('model_type', '알 수 없음')
                if model == "전체" or result['model_type'] == model:
                    filtered_results.append(result)
            
            return filtered_results
            
        except Exception as e:
            st.error(f"검색 중 오류가 발생했습니다: {str(e)}")
            return []
        finally:
            if 'conn' in locals():
                conn.close()
    
    # 검색 결과 표시
    analyses = get_filtered_analyses(search_title, search_area, search_model)
    
    if analyses:
        # 날짜별 그룹화
        from itertools import groupby
        from datetime import datetime
        
        def get_date_str(analysis):
            return analysis['created_at'].strftime('%Y-%m-%d')
        
        grouped_analyses = groupby(analyses, key=get_date_str)
        
        for date, group in grouped_analyses:
            with st.expander(f"📅 {date}", expanded=True):
                for analysis in group:
                    with st.container():
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"#### {analysis['title']}")
                            st.info(f"모델: {analysis['model_type']} | 영역: {analysis['area']}")
                        with col2:
                            if st.button("상세 보기", key=f"view_{analysis['analysis_id']}"):
                                detail = get_toc_analysis_detail(analysis['analysis_id'])
                                st.session_state.selected_detail = detail
                        st.markdown("---")
        
        # 선택된 분석 상세 정보 표시
        if 'selected_detail' in st.session_state:
            detail = st.session_state.selected_detail
            with st.expander("상세 분석 내용", expanded=True):
                st.markdown(f"### {detail['title']}")
                current_state = json.loads(detail['current_state'])
                st.info(f"모델: {current_state.get('model_type', '알 수 없음')}")
                st.write(f"분석 영역: {detail['area']}")
                st.write(f"작성일: {detail['created_at'].strftime('%Y-%m-%d %H:%M')}")
                
                st.markdown("### 입력 데이터")
                st.json(current_state.get('input_data', {}))
                
                st.markdown("### AI 분석 결과")
                solutions = json.loads(detail['solutions'])
                st.write(solutions.get('ai_analysis', '분석 결과가 없습니다.'))
    else:
        st.info("검색 결과가 없습니다.")

def main():
    st.title("🔄 제약이론(TOC) 분석 시스템")
    
    # 초기 탭 상태 설정
    if 'active_tab' not in st.session_state:
        st.session_state.active_tab = 0  # 첫 번째 탭을 기본값으로
    
    # 탭 생성
    tab1, tab2, tab3 = st.tabs(["TOC 모델 선택", "분석 수행", "결과 조회"])
    
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