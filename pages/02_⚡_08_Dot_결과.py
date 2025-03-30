import streamlit as st
import mysql.connector
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="Dot Collector - 결과 분석",
    page_icon="📊",
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

def get_meetings():
    """모든 회의 목록 조회"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                m.*,
                COUNT(DISTINCT i.idea_id) as idea_count,
                (
                    SELECT COUNT(*)
                    FROM dot_ideas i2
                    LEFT JOIN dot_ratings r ON i2.idea_id = r.idea_id
                    WHERE i2.meeting_id = m.meeting_id
                ) as rating_count,
                ea.area_name as primary_area
            FROM dot_meetings m
            LEFT JOIN dot_ideas i ON m.meeting_id = i.meeting_id
            LEFT JOIN dot_expertise_areas ea ON m.primary_area_id = ea.area_id
            GROUP BY m.meeting_id
            ORDER BY m.created_at DESC
        """)
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def get_meeting_results(meeting_id):
    """회의 결과 상세 조회 - 전문성 가중치 반영"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                i.*,
                uc.user_name,
                uc.credibility_score as base_credibility,
                COALESCE(ue.expertise_score, 1.0) as expertise_score,
                m.primary_area_id,
                ea.area_name,
                i.category,
                COUNT(DISTINCT r.rating_id) as rating_count,
                -- 기본 평균
                AVG(r.rating_value) as raw_avg_rating,
                -- 전문성 가중 평균
                SUM(r.rating_value * r.expertise_score * r.credibility_score) / 
                    NULLIF(SUM(r.expertise_score * r.credibility_score), 0) as weighted_avg_rating,
                -- 평가 유형별 가중 평균
                AVG(CASE WHEN r.rating_type = 'agreement' 
                    THEN r.rating_value * r.expertise_score * r.credibility_score END) /
                    NULLIF(AVG(CASE WHEN r.rating_type = 'agreement' 
                    THEN r.expertise_score * r.credibility_score END), 0) as weighted_agreement,
                AVG(CASE WHEN r.rating_type = 'feasibility' 
                    THEN r.rating_value * r.expertise_score * r.credibility_score END) /
                    NULLIF(AVG(CASE WHEN r.rating_type = 'feasibility' 
                    THEN r.expertise_score * r.credibility_score END), 0) as weighted_feasibility,
                AVG(CASE WHEN r.rating_type = 'impact' 
                    THEN r.rating_value * r.expertise_score * r.credibility_score END) /
                    NULLIF(AVG(CASE WHEN r.rating_type = 'impact' 
                    THEN r.expertise_score * r.credibility_score END), 0) as weighted_impact
            FROM dot_ideas i
            JOIN dot_user_credibility uc ON i.user_id = uc.user_id
            JOIN dot_meetings m ON i.meeting_id = m.meeting_id
            JOIN dot_expertise_areas ea ON m.primary_area_id = ea.area_id
            LEFT JOIN dot_user_expertise ue ON i.user_id = ue.user_id 
                AND m.primary_area_id = ue.area_id
            LEFT JOIN dot_ratings r ON i.idea_id = r.idea_id
            WHERE i.meeting_id = %s
            GROUP BY i.idea_id
            ORDER BY weighted_avg_rating DESC
        """, (meeting_id,))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

def check_ratings_data(meeting_id):
    """평가 데이터 확인"""
    conn = connect_to_db()
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT 
                r.rating_id,
                r.idea_id,
                r.rating_type,
                r.rating_value,
                r.rater_id,
                i.meeting_id
            FROM dot_ratings r
            JOIN dot_ideas i ON r.idea_id = i.idea_id
            WHERE i.meeting_id = %s
        """, (meeting_id,))
        ratings = cursor.fetchall()
        return ratings
    finally:
        cursor.close()
        conn.close()

def main():
    st.title("📊 Dot Collector - 결과 분석")
    
    # 회의 선택
    meetings = get_meetings()
    if not meetings:
        st.info("분석할 회의가 없습니다.")
        return
    
    meeting = st.selectbox(
        "분석할 회의를 선택하세요",
        meetings,
        format_func=lambda x: (
            f"{x['title']} ({x['created_at'].strftime('%Y-%m-%d %H:%M')}) "
            f"- {x.get('primary_area', '분야 미지정')} "
            f"- {'진행 중' if x['status'] == 'active' else '종료됨'}"
        )
    )
    
    # 회의 정보 표시
    st.write("## 📌 회의 정보")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.write("**회의 제목:**", meeting['title'])
        st.write("**회의 설명:**", meeting['description'])
    with col2:
        st.write("**주요 분야:**", meeting.get('primary_area', '미지정'))
        st.write("**상태:**", '진행 중' if meeting['status'] == 'active' else '종료됨')
    with col3:
        st.write("**생성일:**", meeting['created_at'].strftime('%Y-%m-%d %H:%M'))
        st.write("**생성자:**", meeting.get('created_by', '미지정'))
    
    st.divider()
    
    # 결과 데이터 가져오기
    results = get_meeting_results(meeting['meeting_id'])
    if not results:
        st.warning("이 회의에는 아직 의견이 없습니다.")
        return
    
    # 데이터프레임 생성 및 NaN 처리
    df = pd.DataFrame(results)
    score_cols = ['weighted_agreement', 'weighted_feasibility', 'weighted_impact']
    df[score_cols] = df[score_cols].fillna(0)
    
    # 1. 종합 통계
    st.write("## 💫 종합 통계")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("총 의견 수", len(results))
    with col2:
        total_ratings = df['rating_count'].sum()
        st.metric("총 평가 수", total_ratings)
    with col3:
        st.metric("참여자 수", df['user_name'].nunique())
    with col4:
        avg_credibility = df['base_credibility'].mean()
        st.metric("평균 신뢰도", f"{avg_credibility:.2f}")
    
    # 2. 카테고리별 분석
    st.write("## 📑 카테고리별 분석")
    category_counts = df['category'].value_counts()
    fig_category = px.pie(
        values=category_counts.values,
        names=category_counts.index,
        title="의견 카테고리 분포"
    )
    st.plotly_chart(fig_category, key="category_pie_chart")
    
    # 3. 평가 점수 분포
    st.write("## 📈 평가 점수 분포")
    score_cols = ['weighted_agreement', 'weighted_feasibility', 'weighted_impact']
    score_names = ['동의도', '실현가능성', '영향력']
    
    fig_scores = go.Figure()
    
    # 기본 평균과 가중 평균 박스플롯
    for col, name in zip(score_cols, score_names):
        values = df[df[col] > 0][col].tolist()
        if values:
            fig_scores.add_trace(go.Box(
                y=values,
                name=name,
                boxpoints='all',
                jitter=0.3,
                pointpos=-1.8
            ))
    
    fig_scores.update_layout(
        title="평가 점수 분포 (전문성 가중치 적용)",
        yaxis_title="점수",
        showlegend=True
    )
    st.plotly_chart(fig_scores, use_container_width=True)
    
    # 4. 상세 의견 목록
    st.write("## 📋 상세 의견 목록")
    
    # 정렬 기준 선택
    sort_by = st.selectbox(
        "정렬 기준",
        ['동의도', '실현가능성', '영향력', '신뢰도'],
        format_func=lambda x: f"{x} 높은 순"
    )
    
    sort_dict = {
        '동의도': 'weighted_agreement',
        '실현가능성': 'weighted_feasibility',
        '영향력': 'weighted_impact',
        '신뢰도': 'base_credibility'
    }
    
    df_sorted = df.sort_values(sort_dict[sort_by], ascending=False)
    
    for idx, row in df_sorted.iterrows():
        # 전문성 점수 계산 (기본값 1.0 사용)
        expertise_score = float(row.get('expertise_score', 1.0))
        effective_score = expertise_score * row['base_credibility']
        
        with st.expander(
            f"{row['category'].upper()}: {row['idea_text'][:50]}... "
            f"(by {row['user_name']} | {row['area_name']} 분야 영향력: {effective_score:.2f})"
        ):
            st.write(f"**전체 의견:** {row['idea_text']}")
            st.write(
                f"**작성자:** {row['user_name']} "
                f"(기본 신뢰도: {row['base_credibility']:.2f}, "
                f"{row['area_name']} 전문성: {expertise_score:.2f}, "
                f"실제 영향력: {effective_score:.2f})"
            )
            st.write(f"**평가 수:** {row['rating_count']}")
            
            # 평가 점수 차트
            scores = {
                '동의도': row['weighted_agreement'],
                '실현가능성': row['weighted_feasibility'],
                '영향력': row['weighted_impact']
            }
            
            fig_radar = go.Figure()
            fig_radar.add_trace(go.Scatterpolar(
                r=list(scores.values()),
                theta=list(scores.keys()),
                fill='toself'
            ))
            
            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 5]
                    )
                ),
                showlegend=False
            )
            st.plotly_chart(fig_radar, key=f"radar_chart_{row['idea_id']}")

if __name__ == "__main__":
    main() 