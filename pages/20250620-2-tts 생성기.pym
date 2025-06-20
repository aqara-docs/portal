import streamlit as st
import os
from openai import OpenAI
import base64

st.set_page_config(page_title="음성 번역 생성기", page_icon="🎙️", layout="wide")

def translate_text(client, text, source_language, target_language, custom_prompt=""):
    """텍스트를 지정된 언어로 번역하거나 처리하는 함수"""
    try:
        # 언어 이름 매핑
        language_names = {
            "한국어": "Korean",
            "영어": "English",
            "중국어": "Chinese",
            "일본어": "Japanese"
        }
        
        # 원문 언어와 목표 언어가 같고 커스텀 프롬프트가 있는 경우
        if source_language == target_language and custom_prompt and custom_prompt.strip():
            system_prompt = "You are a text processing specialist."
            user_message = f"Process the following {language_names[source_language]} text according to these instructions:\n\n[Instructions]\n{custom_prompt.strip()}\n\nText:\n{text}\n\nReturn the processed text maintaining the original language ({language_names[source_language]}) but following the given instructions."
            
        # 원문 언어와 목표 언어가 같고 커스텀 프롬프트가 없는 경우
        elif source_language == target_language:
            return text  # 원문 그대로 반환
            
        # 실제 번역이 필요한 경우
        else:
            system_prompt = "You are a professional translator."
            if custom_prompt:
                system_prompt = f"{system_prompt}\n{custom_prompt}"
            
            user_message = f"Translate the following text from {language_names[source_language]} to {language_names[target_language]}. Keep the original meaning and nuance"
            
            if custom_prompt and custom_prompt.strip():
                user_message += f"\n\n[Important: Please follow these additional instructions]\n{custom_prompt.strip()}"
            
            user_message += f":\n\n{text}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.3
        )
        
        return response.choices[0].message.content
    except Exception as e:
        st.error(f"번역 중 오류 발생: {str(e)}")
        return None

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
    st.title("🎙️ 음성 번역 생성기")
    
    # 사이드바에 설명 추가
    with st.sidebar:
        st.markdown("""
        ### 💡 사용 방법
        1. 원문 텍스트를 입력하세요
        2. 번역할 언어를 선택하세요
        3. 원하는 음성 타입을 선택하세요
        4. 필요한 경우 AI 지시 프롬프트를 입력하세요
        5. '번역 및 음성 생성하기' 버튼을 클릭하세요
        
        ### 🎯 특징
        - 다국어 번역 지원
        - 다양한 목소리 톤 지원
        - 자연스러운 음성 합성
        - AI 프롬프트 커스터마이징
        
        ### ⚠️ 주의사항
        - 한 번에 최대 4000자까지 변환 가능
        - API 키가 필요합니다
        """)
    
    # 메인 영역
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("원문 입력")
        text_input = st.text_area(
            "텍스트를 입력하세요",
            height=200,
            placeholder="여기에 번역할 텍스트를 입력하세요..."
        )
        
        col_lang1, col_lang2 = st.columns(2)
        with col_lang1:
            source_language = st.selectbox(
                "원문 언어",
                ["한국어", "영어", "중국어", "일본어"]
            )
        with col_lang2:
            target_language = st.selectbox(
                "번역할 언어",
                ["한국어", "영어", "중국어", "일본어"]
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
        
        custom_prompt = st.text_area(
            "AI 지시 프롬프트 (선택사항)",
            height=100,
            placeholder="번역 시 특별한 지시사항이 있다면 입력하세요..."
        )
    
    with col2:
        st.subheader("번역된 텍스트")
        translated_placeholder = st.empty()
        audio_placeholder = st.empty()
    
    if st.button("번역 및 음성 생성하기", type="primary"):
        if not text_input.strip():
            st.warning("텍스트를 입력해주세요.")
            return
            
        # OpenAI 클라이언트 초기화
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openai_key or openai_key.strip() == '' or openai_key == 'NA':
            st.error("OpenAI API 키가 올바르지 않습니다.")
            return
            
        client = OpenAI(api_key=openai_key)
        
        with st.spinner("번역 및 음성을 생성하고 있습니다..."):
            # 번역 수행
            translated_text = translate_text(client, text_input, source_language, target_language, custom_prompt)
            if translated_text:
                translated_placeholder.text_area(
                    "번역된 텍스트",
                    value=translated_text,
                    height=200,
                    disabled=True
                )
                
                # 음성 생성
                audio_html = text_to_speech(translated_text, voice_type)
                if audio_html:
                    audio_placeholder.markdown("### 생성된 음성")
                    audio_placeholder.markdown(audio_html, unsafe_allow_html=True)
                    st.success("번역 및 음성이 성공적으로 생성되었습니다!")

if __name__ == "__main__":
    main() 