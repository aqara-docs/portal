import streamlit as st
import requests
import os
from dotenv import load_dotenv
import random
import time

# .env에서 KAKAO_API 키 불러오기
load_dotenv()
KAKAO_API_KEY = os.getenv("KAKAO_API")
headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}

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
st.title("🍽️ 도보 맛집 추천 (카카오맵 실시간)")

# UI 입력
with st.form("search_form"):
    address = st.text_input("회사 위치(주소)", "서울 특별시 서초구 강남대로41길 15-19 (서초동)")
    keyword_input = st.text_input("검색 키워드 (여러 개 입력 시 ,로 구분)", "맛집")
    radius = st.slider("검색 반경(m)", 100, 2000, 300, 100)
    size = st.slider("추천 개수", 1, 10, 3)
    submitted = st.form_submit_button("맛집 추천 받기")

if submitted:
    st.markdown(f"**회사 위치:** {address}")
    st.info(f"아래는 도보 {radius}m 이내의 추천입니다! (키워드: {keyword_input})")
    lat, lon = geocode_address(address)
    if lat is None or lon is None:
        st.error("주소를 찾을 수 없습니다. 다시 입력해 주세요.")
    else:
        try:
            keywords = [k.strip() for k in keyword_input.split(',') if k.strip()]
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
                placeholder.markdown("### 🍽️ 최종 맛집 추천 순위! 🍽️")
                for i, place in enumerate(all_places[:size], 1):
                    st.subheader(f"{i}. 🍽️ {place['place_name']}")
                    st.write(place.get('category_name', ''))
                    st.write(f"주소: {place['address_name']}")
                    st.markdown(f"[카카오맵에서 보기]({place['place_url']})")
                    st.markdown("---")
        except Exception as e:
            st.error(f"API 호출 중 오류가 발생했습니다: {e}")
else:
    st.caption("회사 위치, 키워드(여러 개는 ,로 구분), 반경을 입력하고 '맛집 추천 받기'를 눌러주세요.") 