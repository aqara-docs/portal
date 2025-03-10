import streamlit as st
import mysql.connector
import pandas as pd
import plotly.express as px
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="Dot Collector - 신뢰도 관리",
    page_icon="⭐",
    layout="wide"
)

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

def get_user_stats():
    """사용자별 통계 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                uc.*,
                COUNT(DISTINCT i.idea_id) as ideas_given,
                COUNT(DISTINCT r.rating_id) as ratings_given,
                AVG(CASE 
                    WHEN r2.rating_type = 'agreement' 
                    THEN r2.rating_value 
                END) as avg_agreement_received,
                AVG(CASE 
                    WHEN r2.rating_type = 'feasibility' 
                    THEN r2.rating_value 
                END) as avg_feasibility_received,
                AVG(CASE 
                    WHEN r2.rating_type = 'impact' 
                    THEN r2.rating_value 
                END) as avg_impact_received
            FROM dot_user_credibility uc
            LEFT JOIN dot_ideas i ON uc.user_id = i.user_id
            LEFT JOIN dot_ratings r ON uc.user_id = r.rater_id
            LEFT JOIN dot_ideas i2 ON uc.user_id = i2.user_id
            LEFT JOIN dot_ratings r2 ON i2.idea_id = r2.idea_id
            GROUP BY uc.user_id
            ORDER BY uc.credibility_score DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def update_credibility_score(user_id, new_score):
    """사용자 신뢰도 점수 업데이트"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE dot_user_credibility 
            SET credibility_score = %s
            WHERE user_id = %s
        """, (new_score, user_id))
        
        conn.commit()
        return True, "신뢰도 점수가 성공적으로 업데이트되었습니다!"
    except mysql.connector.Error as err:
        return False, f"신뢰도 점수 업데이트 중 오류가 발생했습니다: {err}"
    finally:
        cursor.close()
        conn.close()

def calculate_suggested_credibility(user):
    """사용자의 제안 신뢰도 점수 계산"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 1. 평가 받은 점수 분석
        cursor.execute("""
            SELECT 
                CAST(AVG(r.rating_value) AS FLOAT) as avg_rating,
                COUNT(*) as rating_count
            FROM dot_ideas i
            LEFT JOIN dot_ratings r ON i.idea_id = r.idea_id
            WHERE i.user_id = %s
        """, (user['user_id'],))
        rating_result = cursor.fetchone()
        
        avg_rating = float(rating_result['avg_rating'] or 0)
        rating_count = rating_result['rating_count']
        
        # 평가 점수 계산 (-0.5 ~ +0.5)
        rating_score = (avg_rating - 2.5) * 0.2
        
        # 2. 평가 참여도 분석
        cursor.execute("""
            SELECT COUNT(*) as given_ratings
            FROM dot_ratings
            WHERE rater_id = %s
        """, (user['user_id'],))
        participation = cursor.fetchone()
        given_ratings = participation['given_ratings']
        
        # 참여도 점수 계산 (0 ~ 0.3)
        participation_score = min(given_ratings / 10, 0.3)
        
        # 3. 기본 점수 (0.7)
        base_score = 0.7
        
        # 최종 점수 계산 (0.2 ~ 1.5 범위)
        suggested_score = max(0.2, min(1.5, base_score + rating_score + participation_score))
        
        return suggested_score
    finally:
        cursor.close()
        conn.close()

def get_user_expertise_stats():
    """사용자별 분야별 통계 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                uc.user_id,
                uc.user_name,
                uc.credibility_score as base_credibility,
                ea.area_id,
                ea.area_name,
                ea.description as area_description,
                ue.expertise_score,
                COUNT(DISTINCT CASE 
                    WHEN m.primary_area_id = ea.area_id 
                    THEN i.idea_id 
                END) as ideas_in_area,
                COUNT(DISTINCT CASE 
                    WHEN m.primary_area_id = ea.area_id 
                    THEN r.rating_id 
                END) as ratings_in_area,
                AVG(CASE 
                    WHEN m.primary_area_id = ea.area_id 
                    AND r2.rating_type = 'agreement' 
                    THEN r2.rating_value 
                END) as avg_agreement_in_area
            FROM dot_user_credibility uc
            CROSS JOIN dot_expertise_areas ea
            LEFT JOIN dot_user_expertise ue 
                ON uc.user_id = ue.user_id 
                AND ea.area_id = ue.area_id
            LEFT JOIN dot_ideas i 
                ON uc.user_id = i.user_id
            LEFT JOIN dot_meetings m 
                ON i.meeting_id = m.meeting_id
            LEFT JOIN dot_ratings r 
                ON uc.user_id = r.rater_id
            LEFT JOIN dot_ratings r2 
                ON i.idea_id = r2.idea_id
            GROUP BY uc.user_id, ea.area_id
            ORDER BY uc.user_name, ea.area_name
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def update_expertise_score(user_id, area_id, new_score):
    """사용자의 분야별 전문성 점수 업데이트"""
    conn = connect_to_db()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO dot_user_expertise (user_id, area_id, expertise_score)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE expertise_score = %s
        """, (user_id, area_id, new_score, new_score))
        
        conn.commit()
        return True, "전문성 점수가 업데이트되었습니다!"
    except mysql.connector.Error as err:
        return False, f"오류 발생: {err}"
    finally:
        cursor.close()
        conn.close()

def get_area_expertise_stats():
    """분야별 전문성 통계 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                ea.area_id,
                ea.area_name,
                ea.description,
                COUNT(DISTINCT ue.user_id) as expert_count,
                COALESCE(AVG(ue.expertise_score), 0) as avg_expertise,
                COALESCE(MAX(ue.expertise_score), 0) as max_expertise,
                COUNT(DISTINCT i.idea_id) as total_ideas,
                COUNT(DISTINCT r.rating_id) as total_ratings,
                COALESCE(AVG(r.rating_value), 0) as avg_rating
            FROM dot_expertise_areas ea
            LEFT JOIN dot_user_expertise ue ON ea.area_id = ue.area_id
            LEFT JOIN dot_meetings m ON m.primary_area_id = ea.area_id
            LEFT JOIN dot_ideas i ON m.meeting_id = i.meeting_id
            LEFT JOIN dot_ratings r ON i.idea_id = r.idea_id
            GROUP BY ea.area_id
            ORDER BY expert_count DESC, avg_expertise DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def main():
    st.title("⭐ Dot Collector - 신뢰도 관리")
    
    # 탭 생성
    tab1, tab2, tab3 = st.tabs(["기본 신뢰도", "분야별 전문성", "분야별 통계"])
    
    # 기본 신뢰도 탭
    with tab1:
        st.write("## 📊 기본 신뢰도 관리")
        # 사용자 통계 가져오기
        user_stats = get_user_stats()
        if not user_stats:
            st.info("등록된 사용자가 없습니다.")
            return
        
        # 데이터프레임 생성
        df = pd.DataFrame(user_stats)
        
        # 1. 전체 통계
        st.write("## 📊 전체 통계")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("총 사용자 수", len(df))
        with col2:
            st.metric("평균 신뢰도", f"{df['credibility_score'].mean():.2f}")
        with col3:
            st.metric("중앙값 신뢰도", f"{df['credibility_score'].median():.2f}")
        
        # 2. 신뢰도 분포
        st.write("## 📈 신뢰도 분포")
        fig = px.histogram(
            df,
            x='credibility_score',
            nbins=20,
            title="사용자 신뢰도 분포"
        )
        st.plotly_chart(fig)
        
        # 3. 사용자별 상세 정보
        st.write("## 👥 사용자별 상세 정보")
        
        for user in user_stats:
            with st.expander(f"{user['user_name']} (현재 신뢰도: {user['credibility_score']:.2f})"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("### 활동 통계")
                    st.write(f"- 제시한 의견 수: {user['ideas_given']}")
                    st.write(f"- 평가 참여 수: {user['ratings_given']}")
                    
                    if user['avg_agreement_received']:
                        st.write(f"- 받은 평균 동의도: {user['avg_agreement_received']:.2f}")
                    if user['avg_feasibility_received']:
                        st.write(f"- 받은 평균 실현가능성: {user['avg_feasibility_received']:.2f}")
                    if user['avg_impact_received']:
                        st.write(f"- 받은 평균 영향력: {user['avg_impact_received']:.2f}")
                
                with col2:
                    st.write("### 신뢰도 관리")
                    suggested_score = calculate_suggested_credibility(user)
                    st.write(f"제안 신뢰도 점수: {suggested_score}")
                    
                    new_score = st.number_input(
                        "신뢰도 점수 수정",
                        min_value=0.0,
                        max_value=3.0,
                        value=float(user['credibility_score']),
                        step=0.1,
                        key=f"score_{user['user_id']}"
                    )
                    
                    if st.button("점수 업데이트", key=f"update_{user['user_id']}"):
                        success, message = update_credibility_score(
                            user['user_id'],
                            new_score
                        )
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)

    # 분야별 전문성 탭
    with tab2:
        st.write("## 🎯 분야별 전문성 관리")
        
        # 사용자별 분야별 통계
        expertise_stats = get_user_expertise_stats()
        if not expertise_stats:
            st.info("데이터가 없습니다.")
            return
        
        # 사용자별 표시
        current_user = None
        for stat in expertise_stats:
            if current_user != stat['user_name']:
                current_user = stat['user_name']
                st.write(f"### 👤 {current_user}")
                st.write(f"기본 신뢰도: {stat['base_credibility']:.2f}")
            
            # 분야별 전문성 관리
            with st.expander(f"📚 {stat['area_name']} ({stat['area_description']})"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("#### 활동 통계")
                    st.write(f"- 해당 분야 의견 수: {stat['ideas_in_area'] or 0}")
                    st.write(f"- 해당 분야 평가 수: {stat['ratings_in_area'] or 0}")
                    if stat['avg_agreement_in_area']:
                        st.write(f"- 받은 평균 동의도: {stat['avg_agreement_in_area']:.2f}")
                
                with col2:
                    st.write("#### 전문성 점수")
                    current_score = stat['expertise_score'] or 1.0
                    new_score = st.number_input(
                        "전문성 점수",
                        min_value=0.0,
                        max_value=5.0,
                        value=float(current_score),
                        step=0.1,
                        help="1.0: 기본, 2.0: 중급, 3.0: 고급, 4.0: 전문가, 5.0: 최고전문가",
                        key=f"expertise_{stat['user_id']}_{stat['area_id']}"
                    )
                    
                    if st.button(
                        "점수 업데이트", 
                        key=f"update_{stat['user_id']}_{stat['area_id']}"
                    ):
                        success, message = update_expertise_score(
                            stat['user_id'],
                            stat['area_id'],
                            new_score
                        )
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                    
                    # 실제 영향력 계산
                    effective_score = new_score * stat['base_credibility']
                    st.write(f"실제 영향력: {effective_score:.2f}")
                    st.caption("실제 영향력 = 전문성 점수 × 기본 신뢰도")

    # 분야별 통계 탭
    with tab3:
        st.write("## 📊 분야별 전문성 통계")
        
        area_stats = get_area_expertise_stats()
        if not area_stats:
            st.info("데이터가 없습니다.")
            return
        
        # 1. 전체 통계 차트
        df_areas = pd.DataFrame(area_stats)
        
        # 분야별 전문가 수 차트
        fig_experts = px.bar(
            df_areas,
            x='area_name',
            y='expert_count',
            title="분야별 전문가 수",
            labels={'area_name': '분야', 'expert_count': '전문가 수'}
        )
        st.plotly_chart(fig_experts)
        
        # 분야별 평균 전문성 점수 차트
        fig_expertise = px.bar(
            df_areas,
            x='area_name',
            y='avg_expertise',
            title="분야별 평균 전문성 점수",
            labels={'area_name': '분야', 'avg_expertise': '평균 전문성'}
        )
        st.plotly_chart(fig_expertise)
        
        # 2. 분야별 상세 정보
        st.write("### 📑 분야별 상세 정보")
        
        for area in area_stats:
            with st.expander(f"📚 {area['area_name']}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("#### 전문가 현황")
                    st.write(f"- 전문가 수: {area['expert_count'] or 0} 명")
                    st.write(f"- 평균 전문성: {f'{area['avg_expertise']:.2f}' if area['avg_expertise'] else '0.00'}")
                    st.write(f"- 최고 전문성: {f'{area['max_expertise']:.2f}' if area['max_expertise'] else '0.00'}")
                
                with col2:
                    st.write("#### 활동 통계")
                    st.write(f"- 총 의견 수: {area['total_ideas'] or 0} 개")
                    st.write(f"- 총 평가 수: {area['total_ratings'] or 0} 개")
                    if area['avg_rating']:
                        st.write(f"- 평균 평가 점수: {area['avg_rating']:.2f}")
                    else:
                        st.write("- 평균 평가 점수: 0.00")
                
                # 해당 분야 전문가 목록
                st.write("#### 🎓 전문가 목록")
                experts = get_area_experts(area['area_id'])
                if experts:
                    expert_df = pd.DataFrame(experts)
                    expert_df = expert_df.sort_values('expertise_score', ascending=False)
                    
                    st.dataframe(
                        expert_df[['user_name', 'expertise_score', 'total_ideas', 'total_ratings']],
                        column_config={
                            'user_name': '이름',
                            'expertise_score': '전문성 점수',
                            'total_ideas': '의견 수',
                            'total_ratings': '평가 수'
                        }
                    )
                else:
                    st.info("등록된 전문가가 없습니다.")

def get_area_experts(area_id):
    """분야별 전문가 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                uc.user_name,
                ue.expertise_score,
                COUNT(DISTINCT i.idea_id) as total_ideas,
                COUNT(DISTINCT r.rating_id) as total_ratings
            FROM dot_user_expertise ue
            JOIN dot_user_credibility uc ON ue.user_id = uc.user_id
            LEFT JOIN dot_ideas i ON uc.user_id = i.user_id
            LEFT JOIN dot_meetings m ON i.meeting_id = m.meeting_id 
                AND m.primary_area_id = ue.area_id
            LEFT JOIN dot_ratings r ON i.idea_id = r.idea_id
            WHERE ue.area_id = %s
            GROUP BY uc.user_id
            HAVING ue.expertise_score >= 1.0
        """, (area_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main() 