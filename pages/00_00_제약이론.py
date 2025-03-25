import streamlit as st
import pandas as pd
from datetime import datetime
import mysql.connector
import os
from dotenv import load_dotenv
import json

load_dotenv()

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

def save_toc_analysis(title, area, current_state, constraints, solutions, implementation_plan):
    """TOC 분석 결과를 DB에 저장"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor()
        
        insert_query = """
        INSERT INTO toc_analysis (
            title, area, current_state, constraints, solutions, 
            implementation_plan, created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, NOW())
        """
        
        cursor.execute(insert_query, (
            title,
            area,
            json.dumps(current_state, ensure_ascii=False),
            json.dumps(constraints, ensure_ascii=False),
            json.dumps(solutions, ensure_ascii=False),
            json.dumps(implementation_plan, ensure_ascii=False)
        ))
        
        conn.commit()
        return True, "분석이 성공적으로 저장되었습니다."
        
    except Exception as e:
        return False, f"저장 중 오류가 발생했습니다: {str(e)}"
        
    finally:
        if conn:
            conn.close()

def get_toc_analyses():
    """저장된 TOC 분석 목록 조회"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT analysis_id, title, area, created_at 
            FROM toc_analysis 
            ORDER BY created_at DESC
        """)
        
        return cursor.fetchall()
        
    except Exception as e:
        st.error(f"데이터 조회 중 오류 발생: {str(e)}")
        return []
        
    finally:
        if conn:
            conn.close()

def get_toc_analysis_detail(analysis_id):
    """특정 TOC 분석의 상세 내용 조회"""
    try:
        conn = connect_to_db()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT * FROM toc_analysis 
            WHERE analysis_id = %s
        """, (analysis_id,))
        
        result = cursor.fetchone()
        if result:
            result['current_state'] = json.loads(result['current_state'])
            result['constraints'] = json.loads(result['constraints'])
            result['solutions'] = json.loads(result['solutions'])
            result['implementation_plan'] = json.loads(result['implementation_plan'])
        return result
        
    except Exception as e:
        st.error(f"상세 정보 조회 중 오류 발생: {str(e)}")
        return None
        
    finally:
        if conn:
            conn.close()

def main():
    st.title("🔄 제약이론(TOC) 분석 시스템")
    
    # 적용 영역 정의
    areas = {
        "마케팅": {
            "description": "마케팅 활동의 제약 요인 분석",
            "examples": ["고객 확보", "브랜드 인지도", "마케팅 ROI", "채널 효율성"]
        },
        "세일즈": {
            "description": "영업/판매 프로세스의 제약 분석",
            "examples": ["리드 전환율", "영업 사이클", "계약 성사율", "고객 이탈"]
        },
        "운영": {
            "description": "전반적인 운영 프로세스의 제약 분석",
            "examples": ["업무 효율성", "자원 활용", "의사결정 프로세스", "조직 구조"]
        },
        "생산": {
            "description": "생산 시스템의 제약 요인 분석",
            "examples": ["생산 용량", "품질 관리", "설비 효율", "불량률"]
        },
        "물류": {
            "description": "물류/유통 시스템의 제약 분석",
            "examples": ["배송 시간", "재고 회전율", "물류 비용", "공급망 효율성"]
        },
        "재고관리": {
            "description": "재고 시스템의 제약 요인 분석",
            "examples": ["재고 수준", "발주 프로세스", "보관 비용", "재고 정확도"]
        }
    }

    tab1, tab2 = st.tabs(["TOC 분석", "분석 결과 조회"])
    
    with tab1:
        st.header("새로운 TOC 분석")
        
        with st.form("toc_analysis_form"):
            title = st.text_input("분석 제목")
            
            # 적용 영역 선택
            area = st.selectbox(
                "적용 영역",
                list(areas.keys()),
                format_func=lambda x: f"{x} - {areas[x]['description']}"
            )
            
            if area:
                st.info(f"""
                **{area}** 영역의 일반적인 제약 요인 예시:
                {', '.join(areas[area]['examples'])}
                """)
            
            # 현재 상태 분석
            st.subheader("1️⃣ 현재 상태 분석")
            current_process = st.text_area("현재 프로세스 설명")
            performance_metrics = st.text_area("주요 성과 지표")
            current_issues = st.text_area("현재 문제점")
            
            # 제약 요인 식별
            st.subheader("2️⃣ 제약 요인 식별")
            physical_constraints = st.text_area("물리적 제약 요인")
            policy_constraints = st.text_area("정책적 제약 요인")
            behavioral_constraints = st.text_area("행동적 제약 요인")
            
            # 해결 방안
            st.subheader("3️⃣ 해결 방안 도출")
            constraint_solutions = st.text_area("제약 해결 방안")
            process_improvements = st.text_area("프로세스 개선 방안")
            system_changes = st.text_area("시스템 변경 사항")
            
            # 실행 계획
            st.subheader("4️⃣ 실행 계획")
            col1, col2 = st.columns(2)
            
            with col1:
                short_term = st.text_area("단기 실행 계획 (1-3개월)")
                mid_term = st.text_area("중기 실행 계획 (3-6개월)")
            
            with col2:
                long_term = st.text_area("장기 실행 계획 (6개월 이상)")
                success_metrics = st.text_area("성공 지표")
            
            submitted = st.form_submit_button("분석 저장")
            
            if submitted:
                if not title or not area:
                    st.error("제목과 적용 영역은 필수 입력 항목입니다.")
                    st.stop()
                
                # 데이터 구조화
                current_state = {
                    "process": current_process,
                    "metrics": performance_metrics,
                    "issues": current_issues
                }
                
                constraints = {
                    "physical": physical_constraints,
                    "policy": policy_constraints,
                    "behavioral": behavioral_constraints
                }
                
                solutions = {
                    "constraint_solutions": constraint_solutions,
                    "process_improvements": process_improvements,
                    "system_changes": system_changes
                }
                
                implementation_plan = {
                    "short_term": short_term,
                    "mid_term": mid_term,
                    "long_term": long_term,
                    "success_metrics": success_metrics
                }
                
                # DB 저장
                success, message = save_toc_analysis(
                    title, area, current_state, constraints, 
                    solutions, implementation_plan
                )
                
                if success:
                    st.success(message)
                else:
                    st.error(message)
    
    with tab2:
        st.header("TOC 분석 결과 조회")
        
        analyses = get_toc_analyses()
        if analyses:
            selected_analysis = st.selectbox(
                "조회할 분석 선택",
                analyses,
                format_func=lambda x: f"{x['title']} ({x['area']}) - {x['created_at'].strftime('%Y-%m-%d')}"
            )
            
            if selected_analysis:
                analysis_detail = get_toc_analysis_detail(selected_analysis['analysis_id'])
                
                if analysis_detail:
                    st.markdown(f"## {analysis_detail['title']}")
                    st.markdown(f"**적용 영역**: {analysis_detail['area']}")
                    st.markdown(f"**작성일**: {analysis_detail['created_at'].strftime('%Y-%m-%d')}")
                    
                    # 현재 상태
                    st.subheader("1️⃣ 현재 상태 분석")
                    st.markdown("### 현재 프로세스")
                    st.write(analysis_detail['current_state']['process'])
                    st.markdown("### 성과 지표")
                    st.write(analysis_detail['current_state']['metrics'])
                    st.markdown("### 문제점")
                    st.write(analysis_detail['current_state']['issues'])
                    
                    # 제약 요인
                    st.subheader("2️⃣ 제약 요인")
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.markdown("### 물리적 제약")
                        st.write(analysis_detail['constraints']['physical'])
                    
                    with col2:
                        st.markdown("### 정책적 제약")
                        st.write(analysis_detail['constraints']['policy'])
                    
                    with col3:
                        st.markdown("### 행동적 제약")
                        st.write(analysis_detail['constraints']['behavioral'])
                    
                    # 해결 방안
                    st.subheader("3️⃣ 해결 방안")
                    st.markdown("### 제약 해결 방안")
                    st.write(analysis_detail['solutions']['constraint_solutions'])
                    st.markdown("### 프로세스 개선 방안")
                    st.write(analysis_detail['solutions']['process_improvements'])
                    st.markdown("### 시스템 변경 사항")
                    st.write(analysis_detail['solutions']['system_changes'])
                    
                    # 실행 계획
                    st.subheader("4️⃣ 실행 계획")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("### 단기 계획")
                        st.write(analysis_detail['implementation_plan']['short_term'])
                        st.markdown("### 중기 계획")
                        st.write(analysis_detail['implementation_plan']['mid_term'])
                    
                    with col2:
                        st.markdown("### 장기 계획")
                        st.write(analysis_detail['implementation_plan']['long_term'])
                        st.markdown("### 성공 지표")
                        st.write(analysis_detail['implementation_plan']['success_metrics'])
                    
                    # 분석 결과 다운로드
                    markdown_content = f"""# {analysis_detail['title']} - TOC 분석 보고서

## 기본 정보
- 적용 영역: {analysis_detail['area']}
- 작성일: {analysis_detail['created_at'].strftime('%Y-%m-%d')}

## 1. 현재 상태 분석
### 현재 프로세스
{analysis_detail['current_state']['process']}

### 성과 지표
{analysis_detail['current_state']['metrics']}

### 문제점
{analysis_detail['current_state']['issues']}

## 2. 제약 요인
### 물리적 제약
{analysis_detail['constraints']['physical']}

### 정책적 제약
{analysis_detail['constraints']['policy']}

### 행동적 제약
{analysis_detail['constraints']['behavioral']}

## 3. 해결 방안
### 제약 해결 방안
{analysis_detail['solutions']['constraint_solutions']}

### 프로세스 개선 방안
{analysis_detail['solutions']['process_improvements']}

### 시스템 변경 사항
{analysis_detail['solutions']['system_changes']}

## 4. 실행 계획
### 단기 계획 (1-3개월)
{analysis_detail['implementation_plan']['short_term']}

### 중기 계획 (3-6개월)
{analysis_detail['implementation_plan']['mid_term']}

### 장기 계획 (6개월 이상)
{analysis_detail['implementation_plan']['long_term']}

### 성공 지표
{analysis_detail['implementation_plan']['success_metrics']}
"""
                    
                    st.download_button(
                        label="분석 보고서 다운로드",
                        data=markdown_content,
                        file_name=f"{analysis_detail['title']}_TOC분석보고서.md",
                        mime="text/markdown"
                    )
        else:
            st.info("저장된 TOC 분석이 없습니다. '분석' 탭에서 새로운 분석을 시작해주세요.")

if __name__ == "__main__":
    main() 