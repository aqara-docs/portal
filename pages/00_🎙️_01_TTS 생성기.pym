import streamlit as st
import os
from openai import OpenAI
import base64

st.set_page_config(page_title="음성 생성기", page_icon="🎙️", layout="wide")

def text_to_speech(text, voice_type):
    """텍스트를 음성으로 변환하는 함수"""
    try:
        # OpenAI API 키 검증
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openai_key or openai_key.strip() == '' or openai_key == 'NA':
            st.error("OpenAI API 키가 올바르지 않습니다.")
            return None
            
        client = OpenAI(api_key=openai_key)
        
        # 음성 설정
        voice_settings = {
            "남성 (깊은 목소리)": "onyx",
            "남성 (중간 톤)": "echo",
            "여성 (밝은 목소리)": "nova",
            "여성 (차분한 목소리)": "shimmer",
            "중성적인 목소리": "alloy"
        }
        
        selected_voice = voice_settings.get(voice_type, "alloy")
        
        response = client.audio.speech.create(
            model="tts-1",
            voice=selected_voice,
            input=text
        )
        
        audio_data = response.content
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        audio_html = f'''
            <audio controls>
                <source src="data:audio/mp3;base64,{audio_base64}" type="audio/mp3">
                Your browser does not support the audio element.
            </audio>
        '''
        return audio_html
    except Exception as e:
        st.error(f"음성 변환 중 오류 발생: {str(e)}")
        return None

def main():
    st.title("🎙️ 음성 생성기")
    
    # 사이드바에 설명 추가
    with st.sidebar:
        st.markdown("""
        ### 💡 사용 방법
        1. 음성으로 변환할 텍스트를 입력하세요
        2. 원하는 음성 타입을 선택하세요
        3. '음성 생성하기' 버튼을 클릭하세요
        
        ### 🎯 특징
        - 다양한 목소리 톤 지원
        - 자연스러운 음성 합성
        - 실시간 음성 변환
        
        ### ⚠️ 주의사항
        - 한 번에 최대 4000자까지 변환 가능
        - API 키가 필요합니다
        """)
    
    # 메인 영역
    text_input = st.text_area(
        "텍스트를 입력하세요",
        height=200,
        placeholder="여기에 음성으로 변환할 텍스트를 입력하세요..."
    )
    
    voice_type = st.selectbox(
        "음성 타입을 선택하세요",
        [
            "남성 (깊은 목소리)",
            "남성 (중간 톤)",
            "여성 (밝은 목소리)",
            "여성 (차분한 목소리)",
            "중성적인 목소리"
        ]
    )
    
    if st.button("음성 생성하기", type="primary"):
        if not text_input.strip():
            st.warning("텍스트를 입력해주세요.")
            return
            
        with st.spinner("음성을 생성하고 있습니다..."):
            audio_html = text_to_speech(text_input, voice_type)
            if audio_html:
                st.markdown("### 생성된 음성")
                st.markdown(audio_html, unsafe_allow_html=True)
                st.success("음성이 성공적으로 생성되었습니다!")

if __name__ == "__main__":
    main() 