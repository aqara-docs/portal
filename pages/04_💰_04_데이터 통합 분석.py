import streamlit as st
import pandas as pd
import numpy as np
import io
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Optional
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

st.set_page_config(page_title="데이터 통합 자동분석", layout="wide")

st.title("💰 데이터 통합 자동분석 (비동기 멀티에이전트)")

# 1. 파일 업로드 및 데이터 로딩
data_file = st.file_uploader("분석할 파일을 업로드하세요 (엑셀, CSV, TXT)", type=["csv", "xlsx", "xls", "txt"])

analysis_request = st.text_area(
    "분석 요청사항을 자연어로 입력하세요 (예: '이상치와 트렌드 중심으로 분석', 'A변수별 그룹 통계와 예측', 등)",
    help="분석에 반영할 요청사항이나 궁금한 점을 자유롭게 입력하세요."
)

# --- 에이전트/툴 정의 ---
CLEANING_TOOLS = ["결측치 제거", "이상치 탐지", "데이터 타입 변환"]
STAT_TOOLS = ["기술통계", "상관분석", "그룹별 요약"]
VIS_TOOLS = ["히스토그램", "Boxplot", "Scatterplot"]

# --- 비동기 에이전트 실행 함수 (더미/예시) ---
def cleaning_agent(df, tools, req):
    import time
    log = []
    result = df.copy()
    log.append(f"[정제에이전트] 시작: 선택툴={tools}, 요구사항={req}")
    if "결측치 제거" in tools:
        log.append("결측치 제거 중...")
        result = result.dropna()
        time.sleep(1)
        log.append("결측치 제거 완료")
    if "이상치 탐지" in tools:
        log.append("이상치 탐지 중...")
        # (간단 예시: 3시그마)
        for col in result.select_dtypes(include=[np.number]).columns:
            mean = result[col].mean()
            std = result[col].std()
            outliers = result[(result[col] < mean - 3*std) | (result[col] > mean + 3*std)][col]
            log.append(f"{col} 이상치 {len(outliers)}개 탐지")
        time.sleep(1)
        log.append("이상치 탐지 완료")
    if "데이터 타입 변환" in tools:
        log.append("데이터 타입 변환 중...")
        # (예시: object→category)
        for col in result.select_dtypes(include=["object"]).columns:
            result[col] = result[col].astype("category")
        time.sleep(1)
        log.append("데이터 타입 변환 완료")
    log.append("[정제에이전트] 완료")
    return result, log

def stat_agent(df, tools, req):
    import time
    log = []
    result = {}
    log.append(f"[통계에이전트] 시작: 선택툴={tools}, 요구사항={req}")
    if "기술통계" in tools:
        log.append("기술통계 계산 중...")
        result["기술통계"] = df.describe(include="all")
        time.sleep(1)
        log.append("기술통계 완료")
    if "상관분석" in tools:
        log.append("상관분석 계산 중...")
        num_cols = df.select_dtypes(include=[np.number]).columns
        if len(num_cols) >= 2:
            result["상관분석"] = df[num_cols].corr()
            log.append("상관분석 완료")
        else:
            log.append("상관분석: 수치형 변수 부족")
        time.sleep(1)
    if "그룹별 요약" in tools:
        log.append("그룹별 요약 계산 중...")
        # (예시: 첫 번째 범주형 기준)
        cat_cols = df.select_dtypes(include=["category", "object"]).columns
        if len(cat_cols) > 0:
            result["그룹별 요약"] = df.groupby(cat_cols[0]).mean(numeric_only=True)
            log.append(f"그룹별 요약({cat_cols[0]}) 완료")
        else:
            log.append("그룹별 요약: 범주형 변수 없음")
        time.sleep(1)
    log.append("[통계에이전트] 완료")
    return result, log

def vis_agent(df, tools, req):
    import time
    log = []
    figs = []
    log.append(f"[시각화에이전트] 시작: 선택툴={tools}, 요구사항={req}")
    num_cols = df.select_dtypes(include=[np.number]).columns
    cat_cols = df.select_dtypes(include=["object", "category"]).columns
    if len(num_cols) == 0:
        log.append("수치형 컬럼이 없어 수치형 시각화 불가")
        # 범주형 barplot
        if len(cat_cols) > 0:
            for col in cat_cols:
                vc = df[col].value_counts().head(20)
                if len(vc) > 0:
                    fig, ax = plt.subplots()
                    vc.plot(kind='bar', ax=ax)
                    ax.set_title(f"{col} 상위 빈도")
                    figs.append((f"Barplot: {col}", fig))
                    plt.close(fig)
            log.append("범주형 barplot 생성")
        # 워드클라우드
        try:
            from wordcloud import WordCloud
            text = " ".join(df[cat_cols[0]].dropna().astype(str)) if len(cat_cols) > 0 else ""
            if text:
                wc = WordCloud(width=800, height=400, background_color='white').generate(text)
                fig, ax = plt.subplots(figsize=(8, 4))
                ax.imshow(wc, interpolation='bilinear')
                ax.axis('off')
                ax.set_title(f"워드클라우드: {cat_cols[0]}")
                figs.append((f"워드클라우드: {cat_cols[0]}", fig))
                plt.close(fig)
                log.append("워드클라우드 생성")
        except ImportError:
            log.append("wordcloud 패키지 미설치 - 워드클라우드 생략")
        return figs, log
    if "히스토그램" in tools:
        for col in num_cols:
            fig, ax = plt.subplots()
            sns.histplot(df[col].dropna(), kde=True, ax=ax)
            ax.set_title(f"{col} 분포")
            figs.append((f"히스토그램: {col}", fig))
            plt.close(fig)
        log.append("히스토그램 완료")
        time.sleep(1)
    if "Boxplot" in tools:
        for col in num_cols:
            fig, ax = plt.subplots()
            sns.boxplot(x=df[col], ax=ax)
            ax.set_title(f"{col} Boxplot")
            figs.append((f"Boxplot: {col}", fig))
            plt.close(fig)
        log.append("Boxplot 완료")
        time.sleep(1)
    if "Scatterplot" in tools and len(num_cols) >= 2:
        fig, ax = plt.subplots()
        sns.scatterplot(x=df[num_cols[0]], y=df[num_cols[1]], ax=ax)
        ax.set_title(f"Scatter: {num_cols[0]} vs {num_cols[1]}")
        figs.append((f"Scatter: {num_cols[0]} vs {num_cols[1]}", fig))
        plt.close(fig)
        log.append("Scatterplot 완료")
        time.sleep(1)
    log.append("[시각화에이전트] 완료")
    return figs, log

# --- 비동기 실행 래퍼 ---
async def run_agents_async(df, cleaning_tools, cleaning_req, stat_tools, stat_req, vis_tools, vis_req):
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        cleaning_future = loop.run_in_executor(pool, cleaning_agent, df, cleaning_tools, cleaning_req)
        # cleaning 결과를 통계/시각화에 전달
        cleaning_result, cleaning_log = await cleaning_future
        stat_future = loop.run_in_executor(pool, stat_agent, cleaning_result, stat_tools, stat_req)
        vis_future = loop.run_in_executor(pool, vis_agent, cleaning_result, vis_tools, vis_req)
        stat_result, stat_log = await stat_future
        vis_result, vis_log = await vis_future
    return cleaning_result, cleaning_log, stat_result, stat_log, vis_result, vis_log

if data_file:
    # 파일 유형 판별 및 로딩
    if data_file.name.endswith(".csv"):
        df = pd.read_csv(data_file)
        data_type = "table"
    elif data_file.name.endswith(".xlsx") or data_file.name.endswith(".xls"):
        df = pd.read_excel(data_file)
        data_type = "table"
    elif data_file.name.endswith(".txt"):
        text_data = data_file.read().decode("utf-8")
        data_type = "text"
    else:
        st.error("지원하지 않는 파일 형식입니다.")
        st.stop()

    # 탭 구조
    if data_type == "table":
        # --- UI: 에이전트/툴/요구사항 입력 ---
        with st.form("agent_form"):
            st.markdown("### 1️⃣ 데이터 정제 에이전트")
            cleaning_tools = st.multiselect("정제 툴 선택", CLEANING_TOOLS, default=CLEANING_TOOLS)
            cleaning_req = st.text_area("정제 요구사항 입력", help="예: 결측치는 평균으로 대체, 이상치는 제거 등")
            st.markdown("### 2️⃣ 통계 요약 에이전트")
            stat_tools = st.multiselect("통계 툴 선택", STAT_TOOLS, default=STAT_TOOLS)
            stat_req = st.text_area("통계 요구사항 입력", help="예: 특정 변수 중심 분석 등")
            st.markdown("### 3️⃣ 시각화 에이전트")
            vis_tools = st.multiselect("시각화 툴 선택", VIS_TOOLS, default=VIS_TOOLS)
            vis_req = st.text_area("시각화 요구사항 입력", help="예: 변수별 분포, 상관관계 시각화 등")
            submitted = st.form_submit_button("비동기 멀티에이전트 분석 실행")

        if submitted:
            st.info("🚀 멀티에이전트 분석을 비동기로 실행합니다. 진행 로그가 아래에 표시됩니다.")
            # 비동기 실행
            cleaning_result, cleaning_log, stat_result, stat_log, vis_result, vis_log = asyncio.run(
                run_agents_async(df, cleaning_tools, cleaning_req, stat_tools, stat_req, vis_tools, vis_req)
            )
            # --- 진행 로그/분석 단계/툴 사용 내역 ---
            st.markdown("#### [진행 로그 및 분석 단계]")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.markdown("**정제 에이전트 로그**")
                for l in cleaning_log:
                    st.write(l)
            with col2:
                st.markdown("**통계 에이전트 로그**")
                for l in stat_log:
                    st.write(l)
            with col3:
                st.markdown("**시각화 에이전트 로그**")
                for l in vis_log:
                    st.write(l)
            st.markdown("---")
            # --- 결과 표시 ---
            st.markdown("### 1️⃣ 정제 결과 (샘플)")
            st.dataframe(cleaning_result.head())
            st.markdown("### 2️⃣ 통계 요약 결과")
            for k, v in stat_result.items():
                st.markdown(f"**{k}**")
                st.dataframe(v)
            st.markdown("### 3️⃣ 시각화 결과")
            if vis_result:
                for title, fig in vis_result:
                    st.markdown(f"**{title}**")
                    st.pyplot(fig)
            else:
                st.info("생성된 시각화 결과가 없습니다. (수치형 컬럼 없음 또는 데이터 부족)")

    elif data_type == "text":
        tab1, tab2, tab3 = st.tabs(["텍스트 요약", "감성/트렌드 분석", "AI 인사이트"])
        with tab1:
            st.subheader("텍스트 요약")
            st.write(text_data[:1000] + ("..." if len(text_data) > 1000 else ""))
        with tab2:
            st.subheader("감성/트렌드 분석")
            st.info("AI 기반 감성/트렌드 분석 결과 (LLM 연동 필요)")
            st.markdown("(여기에 감성/트렌드 분석 결과가 표시됩니다. LLM API 연동 필요)")
        with tab3:
            st.subheader("AI 인사이트 및 전문가 조언")
            st.info("AI 분석 중... (LLM 연동 필요)")
            st.markdown("(여기에 AI 분석 결과가 표시됩니다. LLM API 연동 필요)")
else:
    st.info("분석할 파일을 업로드하세요.") 