import streamlit as st
import pandas as pd
import mysql.connector
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

# Set page configuration
st.set_page_config(page_title="Issue Logs 검색", page_icon="🔍", layout="wide")

def connect_to_db():
    try:
        connection = mysql.connector.connect(
            user=os.getenv('SQL_USER'),
            password=os.getenv('SQL_PASSWORD'),
            host=os.getenv('SQL_HOST'),
            database=os.getenv('SQL_DATABASE_NEWBIZ'),
            charset='utf8mb4',
            collation='utf8mb4_general_ci'
        )
        return connection
    except Exception as e:
        st.error(f"데이터베이스 연결 오류: {e}")
        return None

def search_issue_logs(start_date, end_date, 대분류, 소분류, keyword, 진행상태):
    conn = connect_to_db()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # 기본 쿼리 작성
        query = """
        SELECT 
            DATE_FORMAT(등록일자, '%Y-%m-%d') as 등록일자,
            담당자,
            대분류,
            소분류,
            제목,
            이슈내용,
            DATE_FORMAT(업데이트일자, '%Y-%m-%d') as 업데이트일자,
            해결절차,
            진행상태,
            비고1,
            비고2
        FROM issue_logs
        WHERE 등록일자 BETWEEN %s AND %s
        """
        params = [start_date, end_date]
        
        # 조건 추가
        if 대분류 != "전체":
            query += " AND 대분류 = %s"
            params.append(대분류)
        
        if 소분류 != "전체":
            query += " AND 소분류 = %s"
            params.append(소분류)
        
        if 진행상태 != "전체":
            query += " AND 진행상태 = %s"
            params.append(진행상태)
        
        if keyword:
            query += """ AND (
                제목 LIKE %s OR
                이슈내용 LIKE %s OR
                해결절차 LIKE %s OR
                비고1 LIKE %s OR
                비고2 LIKE %s
            )"""
            keyword_param = f"%{keyword}%"
            params.extend([keyword_param] * 5)
        
        query += " ORDER BY 등록일자 DESC, 업데이트일자 DESC"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        return pd.DataFrame(results)
    
    except Exception as e:
        st.error(f"데이터 검색 중 오류 발생: {e}")
        return None
    finally:
        conn.close()

def main():
    st.title("🔍 Issue Logs 검색")
    
    # 검색 필터 컨테이너
    with st.container():
        col1, col2 = st.columns(2)
        
        with col1:
            # 날짜 범위 선택
            start_date = st.date_input(
                "시작일",
                value=datetime.now() - timedelta(days=30),
                max_value=datetime.now()
            )
            
        with col2:
            end_date = st.date_input(
                "종료일",
                value=datetime.now(),
                max_value=datetime.now()
            )
        
        # 검색 필터 행
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            대분류_options = [
                "전체",
                "SCM/물류",
                "품질관리",
                "영업/마케팅",
                "재무/회계",
                "인사/조직",
                "IT/시스템",
                "R&D/기술",
                "생산/제조",
                "법무/규제",
                "전략/기획",
                "고객서비스",
                "기타"
            ]
            selected_대분류 = st.selectbox("대분류", 대분류_options)
        
        with col2:
            소분류_options = {
                "전체": ["전체"],
                "SCM/물류": ["전체", "구매/발주", "입고/검수", "재고관리", "출하/배송", "통관/수출입", "물류센터", "반품/교환", "공급망관리"],
                "품질관리": ["전체", "품질검사", "인증관리", "공정품질", "불량관리", "품질개선", "AS/클레임", "품질문서", "협력사품질"],
                "영업/마케팅": ["전체", "영업관리", "마케팅전략", "광고/홍보", "영업계획", "고객관리", "시장조사", "상품기획", "채널관리", "프로모션"],
                "재무/회계": ["전체", "회계처리", "세무관리", "자금관리", "예산관리", "원가관리", "투자/IR", "채권/채무", "내부통제", "재무분석"],
                "인사/조직": ["전체", "채용", "교육/연수", "평가/보상", "인사관리", "조직문화", "노무관리", "복리후생", "인력계획", "퇴직관리"],
                "IT/시스템": ["전체", "시스템개발", "인프라관리", "보안관리", "데이터관리", "IT지원", "시스템운영", "장애처리", "프로젝트관리"],
                "R&D/기술": ["전체", "연구개발", "기술기획", "특허/지재권", "기술분석", "제품개발", "공정개발", "기술표준", "기술협력"],
                "생산/제조": ["전체", "생산계획", "공정관리", "설비관리", "자재관리", "안전관리", "환경관리", "생산성개선", "외주관리"],
                "법무/규제": ["전체", "계약관리", "법률자문", "규제대응", "소송관리", "준법감시", "인허가", "지적재산", "개인정보"],
                "전략/기획": ["전체", "경영전략", "사업기획", "투자전략", "성과관리", "리스크관리", "조직전략", "해외사업", "신사업개발"],
                "고객서비스": ["전체", "고객지원", "컨설팅", "기술지원", "민원처리", "VOC관리", "서비스품질", "고객만족", "멤버십관리"],
                "기타": ["전체", "대외협력", "홍보/PR", "사회공헌", "총무", "자산관리", "시설관리", "문서관리"]
            }
            selected_소분류 = st.selectbox(
                "소분류",
                소분류_options.get(selected_대분류, ["전체"])
            )
        
        with col3:
            keyword = st.text_input("키워드 검색", placeholder="검색어를 입력하세요")
        
        with col4:
            진행상태_options = ["전체", "접수", "진행중", "완료", "보류"]
            selected_진행상태 = st.selectbox("진행상태", 진행상태_options)
    
    # 검색 버튼
    if st.button("검색", type="primary"):
        df = search_issue_logs(
            start_date,
            end_date,
            selected_대분류,
            selected_소분류,
            keyword,
            selected_진행상태
        )
        
        if df is not None and not df.empty:
            # 검색 결과 표시
            st.success(f"총 {len(df)}개의 이슈가 검색되었습니다.")
            
            # 각 이슈를 확장 가능한 섹션으로 표시
            for idx, row in df.iterrows():
                with st.expander(f"📋 {row['등록일자']} - {row['제목']} ({row['진행상태']})"):
                    col1, col2 = st.columns([2,1])
                    
                    with col1:
                        st.markdown(f"**담당자:** {row['담당자']}")
                        st.markdown(f"**분류:** {row['대분류']} > {row['소분류']}")
                        st.markdown("**이슈내용:**")
                        st.text(row['이슈내용'])
                        st.markdown("**해결절차:**")
                        st.text(row['해결절차'])
                    
                    with col2:
                        st.markdown(f"**업데이트:** {row['업데이트일자']}")
                        st.markdown(f"**진행상태:** {row['진행상태']}")
                        if row['비고1']:
                            st.markdown("**비고1:**")
                            st.text(row['비고1'])
                        if row['비고2']:
                            st.markdown("**비고2:**")
                            st.text(row['비고2'])
        else:
            st.warning("검색 결과가 없습니다.")

if __name__ == "__main__":
    main()
