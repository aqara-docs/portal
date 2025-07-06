import streamlit as st
import os
from openai import OpenAI
from langchain_anthropic import ChatAnthropic
import threading
from concurrent.futures import ThreadPoolExecutor
import time
import base64

st.set_page_config(page_title="다중 번역기", page_icon="🌐", layout="wide")

def get_ai_response(prompt, model_name, system_prompt=""):
    """AI 모델로부터 응답을 받는 함수"""
    try:
        if model_name.startswith('claude'):
            client = ChatAnthropic(
                model=model_name, 
                api_key=os.getenv('ANTHROPIC_API_KEY'), 
                temperature=0.7, 
                max_tokens=8192
            )
            response = client.invoke([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ])
            return response.content if hasattr(response, 'content') else str(response)
        else:
            openai_key = os.getenv('OPENAI_API_KEY')
            if not openai_key or openai_key.strip() == '' or openai_key == 'NA':
                raise ValueError("OpenAI API 키가 올바르지 않습니다.")
            
            client = OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=8192,
                temperature=0.7
            )
            return response.choices[0].message.content
    except Exception as e:
        return f"오류 발생: {str(e)}"

def text_to_speech(text, voice_type):
    """텍스트를 음성으로 변환하는 함수"""
    try:
        # OpenAI API 키 검증
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openai_key or openai_key.strip() == '' or openai_key == 'NA':
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
        return None

def translate_or_answer(model_name, source_text, prompt, source_language, target_language, is_question=False):
    """텍스트를 번역하거나 질문에 답변하는 함수"""
    try:
        # 언어 이름 매핑
        language_names = {
            "한국어": "Korean",
            "영어": "English", 
            "중국어": "Chinese",
            "일본어": "Japanese",
            "프랑스어": "French",
            "독일어": "German",
            "스페인어": "Spanish",
            "이탈리아어": "Italian",
            "러시아어": "Russian",
            "포르투갈어": "Portuguese"
        }
        
        # 원문이 없고 질문인 경우 - 완전한 LLM 기능
        if is_question:
            # 언어 지정이 한국어가 아닌 경우에만 언어 요청
            if target_language != "한국어":
                system_prompt = f"You are a helpful AI assistant. Please respond in {language_names[target_language]} language."
                user_message = f"Please answer the following question or request in {language_names[target_language]}:\n\n{prompt}"
            else:
                # 한국어인 경우 일반적인 AI 어시스턴트로 동작
                system_prompt = "You are a helpful AI assistant."
                user_message = prompt
            
        # 번역인 경우
        else:
            # 원문 언어와 목표 언어가 같고 프롬프트가 있는 경우
            if source_language == target_language and prompt and prompt.strip():
                system_prompt = f"You are a text processing specialist. Always respond in {language_names[target_language]}."
                user_message = f"Process the following {language_names[source_language]} text according to these instructions:\n\n[Instructions]\n{prompt.strip()}\n\nText:\n{source_text}\n\nReturn the processed text in {language_names[target_language]} following the given instructions."
                
            # 원문 언어와 목표 언어가 같고 프롬프트가 없는 경우
            elif source_language == target_language:
                return source_text  # 원문 그대로 반환
                
            # 실제 번역이 필요한 경우
            else:
                system_prompt = f"You are a professional translator. Always translate to {language_names[target_language]}."
                user_message = f"Translate the following text from {language_names[source_language]} to {language_names[target_language]}. Keep the original meaning and nuance"
                
                if prompt and prompt.strip():
                    user_message += f"\n\n[Important: Please follow these additional instructions]\n{prompt.strip()}"
                
                user_message += f":\n\n{source_text}"
        
        return get_ai_response(user_message, model_name, system_prompt)
        
    except Exception as e:
        return f"오류 발생: {str(e)}"

def translate_to_multiple_languages(model_name, source_text, prompt, source_language, target_languages, is_question=False):
    """여러 언어로 동시 번역/답변하는 함수"""
    results = {}
    
    def translate_single(target_lang):
        result = translate_or_answer(model_name, source_text, prompt, source_language, target_lang, is_question)
        return target_lang, result
    
    # ThreadPoolExecutor를 사용하여 동시에 번역 요청
    with ThreadPoolExecutor(max_workers=len(target_languages)) as executor:
        futures = [executor.submit(translate_single, lang) for lang in target_languages]
        
        for future in futures:
            lang, result = future.result()
            results[lang] = result
    
    return results

def main():
    st.title("🌐 다중 번역기")
    
    # 세션 상태 초기화
    if 'selected_model' not in st.session_state:
        st.session_state.selected_model = 'claude-3-7-sonnet-latest'
    
    # 사이드바에 모델 선택과 설명 추가
    with st.sidebar:
        st.markdown("### 🧠 AI 모델 선택")
        
        # 모델 선택
        available_models = []
        has_anthropic_key = os.environ.get('ANTHROPIC_API_KEY') is not None
        if has_anthropic_key:
            available_models.extend([
                'claude-3-7-sonnet-latest',
                'claude-3-5-sonnet-latest', 
                'claude-3-5-haiku-latest',
            ])
        has_openai_key = os.environ.get('OPENAI_API_KEY') is not None
        if has_openai_key:
            available_models.extend(['gpt-4o', 'gpt-4o-mini'])
        
        if not available_models:
            st.sidebar.error("API 키가 설정되지 않았습니다.")
            available_models = ['claude-3-7-sonnet-latest']  # 기본값
        
        selected_model = st.selectbox(
            '🧠 AI 모델 선택',
            options=available_models,
            index=available_models.index(st.session_state.selected_model) if st.session_state.selected_model in available_models else 0,
            help='Claude는 ANTHROPIC_API_KEY, OpenAI는 OPENAI_API_KEY 필요'
        )
        
        if selected_model != st.session_state.selected_model:
            st.session_state.selected_model = selected_model
        
        st.markdown("---")
        
        st.markdown("""
        ### 💡 사용 방법
        
        **번역 모드:**
        1. 원문 텍스트를 입력하세요
        2. 원문 언어를 선택하세요
        3. 번역할 언어들을 선택하세요
        4. 필요시 추가 지시사항을 입력하세요 (선택사항)
        5. '번역하기' 버튼을 클릭하세요
        
        **질문 답변 모드:**
        1. 원문을 비워두세요
        2. 질문/요청사항을 입력하세요
        3. 답변받을 언어들을 선택하세요
        4. '질문하기' 버튼을 클릭하세요
        
        ### 🎯 특징
        - 10개 언어 지원
        - Claude & OpenAI 모델 지원
        - 동시 다중 번역
        - 완전한 LLM 기능
        - 음성 생성 기능
        - 선택적 커스텀 지시사항
        
        ### 🌍 지원 언어
        - 한국어, 영어, 중국어, 일본어
        - 프랑스어, 독일어, 스페인어
        - 이탈리아어, 러시아어, 포르투갈어
        """)
    
    # 메인 영역
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("입력")
        
        # 원문 입력
        source_text = st.text_area(
            "원문 텍스트 (번역 모드)",
            height=150,
            placeholder="번역할 텍스트를 입력하세요. 비워두면 질문 답변 모드가 됩니다.",
            help="원문을 입력하면 번역 모드, 비워두면 질문 답변 모드"
        )
        
        # 프롬프트/질문 입력
        prompt_input = st.text_area(
            "프롬프트/질문 (선택사항)",
            height=100,
            placeholder="번역 지시사항 또는 질문을 입력하세요...",
            help="번역 모드: 특별한 번역 지시사항 (선택사항)\n질문 모드: 답변받고 싶은 질문"
        )
        
        # 모드 자동 감지
        is_question_mode = not source_text.strip()
        mode_display = "🤖 질문 답변 모드" if is_question_mode else "🔄 번역 모드"
        st.info(f"현재 모드: {mode_display}")
        
        # 언어 선택
        available_languages = [
            "한국어", "영어", "중국어", "일본어", "프랑스어", 
            "독일어", "스페인어", "이탈리아어", "러시아어", "포르투갈어"
        ]
        
        if not is_question_mode:
            source_language = st.selectbox(
                "원문 언어",
                available_languages,
                help="원문의 언어를 선택하세요"
            )
        else:
            source_language = "한국어"  # 질문 모드에서는 기본값
        
        target_languages = st.multiselect(
            "번역할 언어들" if not is_question_mode else "답변받을 언어들",
            available_languages,
            default=["영어"] if not is_question_mode else ["한국어"],
            help="여러 언어를 선택할 수 있습니다"
        )
        
        # 음성 생성 옵션
        st.markdown("### 🎙️ 음성 생성 옵션")
        enable_tts = st.checkbox("음성 파일 생성", value=False, help="결과를 음성으로 변환합니다 (OpenAI API 필요)")
        
        if enable_tts:
            voice_type = st.selectbox(
                "음성 타입",
                [
                    "남성 (깊은 목소리)",
                    "남성 (중간 톤)",
                    "여성 (밝은 목소리)",
                    "여성 (차분한 목소리)",
                    "중성적인 목소리"
                ],
                help="OpenAI TTS를 사용한 음성 생성"
            )
        else:
            voice_type = None
    
    with col2:
        st.subheader("결과")
        
        # 버튼
        button_text = "질문하기" if is_question_mode else "번역하기"
        if st.button(button_text, type="primary"):
            # 질문 모드에서는 프롬프트가 필수
            if is_question_mode and not prompt_input.strip():
                st.warning("질문 답변 모드에서는 질문을 입력해주세요.")
                return
            
            # 번역 모드에서는 원문이 필수    
            if not is_question_mode and not source_text.strip():
                st.warning("번역 모드에서는 원문 텍스트를 입력해주세요.")
                return
                
            if not target_languages:
                st.warning("번역할 언어를 최소 하나 선택해주세요.")
                return
                
            # 진행 상황 표시
            progress_text = "질문에 답변하고 있습니다..." if is_question_mode else "번역하고 있습니다..."
            with st.spinner(progress_text):
                start_time = time.time()
                
                # 번역/답변 수행
                results = translate_to_multiple_languages(
                    selected_model, source_text, prompt_input, source_language, target_languages, is_question_mode
                )
                
                end_time = time.time()
                processing_time = round(end_time - start_time, 2)
                
                # 결과 표시
                if results:
                    st.success(f"완료! (처리 시간: {processing_time}초)")
                    
                    # 각 언어별 결과를 탭으로 표시
                    if len(target_languages) > 1:
                        tabs = st.tabs([f"🌍 {lang}" for lang in target_languages])
                        for i, lang in enumerate(target_languages):
                            with tabs[i]:
                                result_text = results.get(lang, "오류 발생")
                                st.text_area(
                                    f"{lang} 결과",
                                    value=result_text,
                                    height=200,
                                    disabled=True
                                )
                                
                                # 음성 생성
                                if enable_tts and voice_type and result_text and not result_text.startswith("오류"):
                                    with st.spinner(f"{lang} 음성 생성 중..."):
                                        audio_html = text_to_speech(result_text, voice_type)
                                        if audio_html:
                                            st.markdown(f"### 🎙️ {lang} 음성")
                                            st.markdown(audio_html, unsafe_allow_html=True)
                                        else:
                                            st.warning("음성 생성 실패 (OpenAI API 키 확인 필요)")
                    else:
                        # 언어가 하나면 바로 표시
                        lang = target_languages[0]
                        result_text = results.get(lang, "오류 발생")
                        st.text_area(
                            f"{lang} 결과",
                            value=result_text,
                            height=200,
                            disabled=True
                        )
                        
                        # 음성 생성
                        if enable_tts and voice_type and result_text and not result_text.startswith("오류"):
                            with st.spinner(f"{lang} 음성 생성 중..."):
                                audio_html = text_to_speech(result_text, voice_type)
                                if audio_html:
                                    st.markdown(f"### 🎙️ {lang} 음성")
                                    st.markdown(audio_html, unsafe_allow_html=True)
                                else:
                                    st.warning("음성 생성 실패 (OpenAI API 키 확인 필요)")
                    
                    # 통계 정보
                    with st.expander("📊 처리 정보"):
                        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                        with col_stat1:
                            st.metric("사용 모델", selected_model)
                        with col_stat2:
                            st.metric("처리 언어 수", len(target_languages))
                        with col_stat3:
                            st.metric("처리 시간", f"{processing_time}초")
                        with col_stat4:
                            if not is_question_mode and source_text:
                                st.metric("원문 길이", f"{len(source_text)}자")
                            else:
                                st.metric("프롬프트 길이", f"{len(prompt_input)}자")

if __name__ == "__main__":
    main() 