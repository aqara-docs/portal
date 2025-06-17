import streamlit as st
import requests
import os
from dotenv import load_dotenv
import random
import time
from openai import OpenAI
from langchain_anthropic import ChatAnthropic

# .env에서 API 키들 불러오기
load_dotenv()
KAKAO_API_KEY = os.getenv("KAKAO_API")
headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}

# AI 모델 선택 및 API 키 확인
def get_available_models():
    available_models = []
    has_anthropic_key = os.environ.get('ANTHROPIC_API_KEY') is not None
    if has_anthropic_key:
        available_models.extend([
            'claude-3-5-sonnet-latest',
            'claude-3-5-haiku-latest',
        ])
    has_openai_key = os.environ.get('OPENAI_API_KEY') is not None
    if has_openai_key:
        available_models.extend(['gpt-4o', 'gpt-4o-mini'])
    if not available_models:
        available_models = ['claude-3-5-sonnet-latest']
    return available_models

# AI 키워드 추천 함수
def ai_recommend_keywords(user_prompt, model_name):
    instruction = (
        "사용자의 요청에 따라 맛집 검색에 적합한 키워드 3-5개를 추천해 주세요. "
        "각 키워드는 카카오맵 검색에 효과적이고, 구체적이어야 합니다. "
        "키워드들은 쉼표(,)로 구분해서 제시해 주세요. "
        "예: 한식, 카페, 파스타, 치킨, 일식"
    )
    
    if model_name.startswith('claude'):
        try:
            client = ChatAnthropic(model=model_name, api_key=os.getenv('ANTHROPIC_API_KEY'), temperature=0.7, max_tokens=200)
            response = client.invoke([
                {"role": "system", "content": "당신은 맛집 검색 키워드 추천 전문가입니다. 사용자의 요청에 맞는 효과적인 검색 키워드를 제안합니다."},
                {"role": "user", "content": f"{instruction}\n\n사용자 요청: {user_prompt}"}
            ])
            return response.content if hasattr(response, 'content') else str(response)
        except Exception as e:
            st.error(f"Claude API 호출 중 오류: {str(e)}")
            return None
    else:
        try:
            openai_key = os.getenv('OPENAI_API_KEY')
            if not openai_key or openai_key.strip() == '' or openai_key == 'NA':
                st.error("OpenAI API 키가 설정되지 않았습니다.")
                return None
            
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "당신은 맛집 검색 키워드 추천 전문가입니다. 사용자의 요청에 맞는 효과적인 검색 키워드를 제안합니다."},
                    {"role": "user", "content": f"{instruction}\n\n사용자 요청: {user_prompt}"}
                ],
                max_tokens=200,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            st.error(f"OpenAI API 호출 중 오류: {str(e)}")
            return None

# AI 맛집 순서 추천 함수
def ai_rank_restaurants(places, user_prompt, model_name):
    if not places:
        return places, "추천할 맛집이 없습니다."
    
    # 맛집 정보를 텍스트로 변환
    places_info = []
    for i, place in enumerate(places, 1):
        info = f"{i}. {place['place_name']} - {place.get('category_name', '')} - {place['address_name']}"
        places_info.append(info)
    
    places_text = "\n".join(places_info)
    
    instruction = (
        "아래 맛집 목록을 사용자의 요청과 선호도에 따라 순위를 매겨 주세요. "
        "각 맛집의 순위와 함께 추천 이유를 간단히 설명해 주세요. "
        "카테고리, 위치, 이름 등을 종합적으로 고려해서 순위를 정해 주세요.\n\n"
        "출력 형식:\n"
        "1. [맛집명] - [추천 이유]\n"
        "2. [맛집명] - [추천 이유]\n"
        "...\n\n"
        "전체 추천 요약: [전체적인 추천 근거와 특징]"
    )
    
    if model_name.startswith('claude'):
        try:
            client = ChatAnthropic(model=model_name, api_key=os.getenv('ANTHROPIC_API_KEY'), temperature=0.3, max_tokens=1500)
            response = client.invoke([
                {"role": "system", "content": "당신은 맛집 추천 전문가입니다. 사용자의 선호도와 상황을 고려해서 맛집 순위를 매기고 이유를 설명합니다."},
                {"role": "user", "content": f"{instruction}\n\n사용자 요청: {user_prompt}\n\n맛집 목록:\n{places_text}"}
            ])
            recommendation_text = response.content if hasattr(response, 'content') else str(response)
            
            # AI 추천 순서대로 맛집 목록 재정렬
            ranked_places = reorder_places_by_ai_recommendation(places, recommendation_text)
            return ranked_places, recommendation_text
        except Exception as e:
            st.error(f"Claude API 호출 중 오류: {str(e)}")
            return places, f"AI 추천 중 오류가 발생했습니다: {str(e)}"
    else:
        try:
            openai_key = os.getenv('OPENAI_API_KEY')
            if not openai_key or openai_key.strip() == '' or openai_key == 'NA':
                st.error("OpenAI API 키가 설정되지 않았습니다.")
                return places, "OpenAI API 키가 설정되지 않았습니다."
            
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "당신은 맛집 추천 전문가입니다. 사용자의 선호도와 상황을 고려해서 맛집 순위를 매기고 이유를 설명합니다."},
                    {"role": "user", "content": f"{instruction}\n\n사용자 요청: {user_prompt}\n\n맛집 목록:\n{places_text}"}
                ],
                max_tokens=1500,
                temperature=0.3
            )
            recommendation_text = response.choices[0].message.content
            
            # AI 추천 순서대로 맛집 목록 재정렬
            ranked_places = reorder_places_by_ai_recommendation(places, recommendation_text)
            return ranked_places, recommendation_text
        except Exception as e:
            st.error(f"OpenAI API 호출 중 오류: {str(e)}")
            return places, f"AI 추천 중 오류가 발생했습니다: {str(e)}"

# AI 추천에 따라 맛집 순서 재정렬
def reorder_places_by_ai_recommendation(places, recommendation_text):
    try:
        # AI 추천 텍스트에서 맛집 이름 순서 추출
        lines = recommendation_text.split('\n')
        ranked_names = []
        
        for line in lines:
            if line.strip() and (line.strip().startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.', '8.', '9.', '10.'))):
                # 맛집 이름 추출 (숫자. 다음부터 - 앞까지)
                parts = line.split(' - ')
                if parts:
                    name_part = parts[0]
                    # 숫자와 점 제거
                    name = name_part.split('.', 1)[-1].strip()
                    ranked_names.append(name)
        
        # 추천 순서대로 맛집 재정렬
        ranked_places = []
        used_indices = set()
        
        for ranked_name in ranked_names:
            for i, place in enumerate(places):
                if i not in used_indices and ranked_name in place['place_name']:
                    ranked_places.append(place)
                    used_indices.add(i)
                    break
        
        # 매칭되지 않은 맛집들 추가
        for i, place in enumerate(places):
            if i not in used_indices:
                ranked_places.append(place)
        
        return ranked_places if ranked_places else places
    except:
        # 재정렬 실패 시 원본 반환
        return places

# 주소 → 좌표 변환 함수 (카카오맵 geocoding API)
def geocode_address(address):
    url = "https://dapi.kakao.com/v2/local/search/address.json"
    params = {"query": address}
    resp = requests.get(url, headers=headers, params=params)
    data = resp.json()
    if data.get('documents'):
        doc = data['documents'][0]
        return float(doc['y']), float(doc['x'])  # 위도, 경도
    return None, None

# 장소 검색 함수
def search_places(query, x, y, radius=500, size=5):
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    params = {
        "query": query,
        "x": x,  # 경도
        "y": y,  # 위도
        "radius": radius,
        "size": size
    }
    resp = requests.get(url, headers=headers, params=params)
    return resp.json()

st.set_page_config(page_title="서초동 맛집 추천", page_icon="🍽️")
st.title("🍽️ AI 맛집 추천 (카카오맵 + AI)")

# AI 모델 선택
available_models = get_available_models()
if 'restaurant_ai_model' not in st.session_state:
    st.session_state.restaurant_ai_model = available_models[0] if available_models else 'claude-3-5-sonnet-latest'

selected_model = st.selectbox(
    'AI 모델 선택',
    options=available_models,
    index=available_models.index(st.session_state.restaurant_ai_model) if st.session_state.restaurant_ai_model in available_models else 0,
    help='Claude(Anthropic)는 ANTHROPIC_API_KEY, OpenAI는 OPENAI_API_KEY 필요'
)
st.session_state.restaurant_ai_model = selected_model

# UI 입력
with st.form("search_form"):
    address = st.text_input("회사 위치(주소)", "서울 특별시 서초구 강남대로41길 15-19 (서초동)")
    
    # AI 프롬프트 입력
    ai_prompt = st.text_area(
        "AI 추천 요청사항", 
        "점심시간에 직장인들이 가기 좋은 맛집을 추천해 주세요. 가성비 좋고 빠르게 식사할 수 있는 곳을 선호합니다.",
        height=100,
        help="어떤 상황, 선호도, 분위기의 맛집을 원하는지 자세히 적어주세요."
    )
    
    col1, col2 = st.columns(2)
    with col1:
        use_ai_keywords = st.checkbox("AI 키워드 추천 사용", value=True)
    with col2:
        use_ai_ranking = st.checkbox("AI 순위 추천 사용", value=True)
    
    if not use_ai_keywords:
        keyword_input = st.text_input("검색 키워드 (여러 개 입력 시 ,로 구분)", "맛집")
    
    radius = st.slider("검색 반경(m)", 100, 2000, 300, 100)
    size = st.slider("추천 개수", 1, 10, 5)
    submitted = st.form_submit_button("🤖 AI 맛집 추천 받기")

if submitted:
    st.markdown(f"**회사 위치:** {address}")
    st.info(f"아래는 도보 {radius}m 이내의 AI 추천입니다!")
    
    lat, lon = geocode_address(address)
    if lat is None or lon is None:
        st.error("주소를 찾을 수 없습니다. 다시 입력해 주세요.")
    else:
        try:
            # 1단계: AI 키워드 추천
            if use_ai_keywords:
                with st.spinner("🤖 AI가 검색 키워드를 추천하고 있습니다..."):
                    ai_keywords = ai_recommend_keywords(ai_prompt, selected_model)
                    if ai_keywords:
                        st.success("✅ AI 추천 키워드")
                        st.write(f"**추천 키워드:** {ai_keywords}")
                        keywords = [k.strip() for k in ai_keywords.split(',') if k.strip()]
                    else:
                        st.warning("AI 키워드 추천에 실패했습니다. 기본 키워드를 사용합니다.")
                        keywords = ["맛집"]
            else:
                keywords = [k.strip() for k in keyword_input.split(',') if k.strip()]
            
            # 맛집 검색
            with st.spinner("🔍 맛집 정보를 검색하고 있습니다..."):
                all_places = []
                place_ids = set()
                for kw in keywords:
                    result = search_places(kw, lon, lat, radius=radius, size=size)
                    for p in result.get('documents', []):
                        # 중복 제거 (id + 주소 기준)
                        unique_id = (p['id'], p['address_name'])
                        if unique_id not in place_ids:
                            all_places.append(p)
                            place_ids.add(unique_id)
                
                if not all_places:
                    st.warning("주변에 맛집 정보가 없습니다. (카카오맵 기준)")
                else:
                    # 2단계: AI 순위 추천
                    if use_ai_ranking:
                        with st.spinner("🤖 AI가 맛집 순위를 추천하고 있습니다..."):
                            ranked_places, recommendation_text = ai_rank_restaurants(all_places[:size], ai_prompt, selected_model)
                            
                        st.success("🎯 AI 맛집 추천 완료!")
                        
                        # AI 추천 이유 표시
                        with st.expander("🤖 AI 추천 이유 보기", expanded=True):
                            st.markdown(recommendation_text)
                        
                        final_places = ranked_places[:size]
                    else:
                        st.success("맛집 후보를 셔플 중입니다! 🍽️")
                        placeholder = st.empty()
                        names = [p['place_name'] for p in all_places]
                        # 룰렛 애니메이션: 1.5초간 20회 셔플
                        for _ in range(20):
                            random.shuffle(names)
                            display = '\n'.join([f"{i+1}. {name}" for i, name in enumerate(names)])
                            placeholder.markdown(f"**맛집 순위 셔플!**\n\n{display}")
                            time.sleep(0.07)
                        # 최종 순서 확정
                        random.shuffle(all_places)
                        final_places = all_places[:size]
                        placeholder.empty()
                    
                    # 최종 맛집 목록 표시
                    st.markdown("### 🍽️ 최종 맛집 추천 순위! 🍽️")
                    for i, place in enumerate(final_places, 1):
                        # 순위에 따른 이모지
                        rank_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🍽️"
                        st.subheader(f"{i}. {rank_emoji} {place['place_name']}")
                        st.write(place.get('category_name', ''))
                        st.write(f"주소: {place['address_name']}")
                        st.markdown(f"[카카오맵에서 보기]({place['place_url']})")
                        st.markdown("---")
                        
        except Exception as e:
            st.error(f"API 호출 중 오류가 발생했습니다: {e}")
else:
    st.caption("회사 위치와 AI 추천 요청사항을 입력하고 '🤖 AI 맛집 추천 받기'를 눌러주세요.") 