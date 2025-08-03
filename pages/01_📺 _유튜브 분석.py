import streamlit as st
import os
import re
import requests
from urllib.parse import urlparse, parse_qs
import yt_dlp
import pandas as pd
from datetime import datetime
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from openai import OpenAI
from langchain_anthropic import ChatAnthropic
import base64

# 페이지 설정
st.set_page_config(
    page_title="YouTube 다운로드 & 분석",
    page_icon="🎥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 제목과 설명
st.title("🎥 YouTube 다운로드 & 분석")

st.markdown("---")

# 세션 상태 초기화
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'download_files' not in st.session_state:
    st.session_state.download_files = {}

def extract_video_id(url):
    """YouTube URL에서 비디오 ID 추출"""
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
        r'youtube\.com\/watch\?.*v=([^&\n?#]+)',
        r'youtu\.be\/([^&\n?#]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def extract_playlist_id(url):
    """YouTube URL에서 재생목록 ID 추출"""
    patterns = [
        r'youtube\.com\/playlist\?list=([^&\n?#]+)',
        r'youtube\.com\/watch\?.*list=([^&\n?#]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def is_playlist_url(url):
    """재생목록 URL인지 확인"""
    return extract_playlist_id(url) is not None

def get_playlist_info(url):
    """재생목록 정보 가져오기"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if 'entries' in info:
                playlist_info = {
                    'title': info.get('title', 'Unknown Playlist'),
                    'uploader': info.get('uploader', 'Unknown'),
                    'video_count': len(info['entries']),
                    'videos': []
                }
                
                for entry in info['entries']:
                    if entry:
                        video_info = {
                            'id': entry.get('id', ''),
                            'title': entry.get('title', 'Unknown'),
                            'duration': entry.get('duration', 0),
                            'uploader': entry.get('uploader', 'Unknown'),
                            'url': f"https://www.youtube.com/watch?v={entry.get('id', '')}"
                        }
                        playlist_info['videos'].append(video_info)
                
                return playlist_info
            else:
                return None
    except Exception as e:
        st.error(f"재생목록 정보 가져오기 실패: {e}")
        return None

def get_video_info(url):
    """YouTube 비디오 정보 가져오기"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Unknown'),
                'view_count': info.get('view_count', 0),
                'upload_date': info.get('upload_date', ''),
                'thumbnail': info.get('thumbnail', ''),
                'description': info.get('description', '')[:200] + '...' if info.get('description') else '',
                'formats': info.get('formats', [])
            }
    except Exception as e:
        st.error(f"비디오 정보 가져오기 실패: {e}")
        return None

def get_available_formats(url):
    """사용 가능한 포맷 목록 가져오기"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            
            video_formats = []
            audio_formats = []
            
            for fmt in formats:
                format_info = {
                    'format_id': fmt.get('format_id', ''),
                    'ext': fmt.get('ext', ''),
                    'filesize': fmt.get('filesize', 0),
                    'height': fmt.get('height', 0),
                    'width': fmt.get('width', 0),
                    'fps': fmt.get('fps', 0),
                    'acodec': fmt.get('acodec', 'none'),
                    'vcodec': fmt.get('vcodec', 'none'),
                }
                
                # 비디오+오디오 포맷 (해상도가 있고 오디오도 있는 경우)
                if (fmt.get('height') and fmt.get('vcodec') != 'none' and 
                    fmt.get('acodec') != 'none'):
                    video_formats.append(format_info)
                
                # 순수 오디오 포맷 (오디오만 있고 비디오가 없는 경우)
                if (fmt.get('acodec') != 'none' and 
                    (fmt.get('vcodec') == 'none' or not fmt.get('height') or fmt.get('height') == 0)):
                    audio_formats.append(format_info)
            
            return video_formats, audio_formats
    except Exception as e:
        st.error(f"포맷 정보 가져오기 실패: {e}")
        return [], []

def get_download_url(url, format_id=None, audio_only=False, min_bitrate=0):
    """YouTube 비디오의 직접 다운로드 URL 가져오기"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            
            if audio_only:
                # 오디오만 다운로드하는 경우 - 더 나은 오디오 포맷 선택
                audio_formats = []
                
                for fmt in formats:
                    # 오디오 코덱이 있고 비디오가 없는 포맷 찾기
                    if (fmt.get('acodec') != 'none' and 
                        (fmt.get('vcodec') == 'none' or not fmt.get('height') or fmt.get('height') == 0)):
                        
                        # 품질별로 정렬 (비트레이트 기준)
                        bitrate = fmt.get('abr', 0) or fmt.get('tbr', 0) or 0
                        audio_formats.append({
                            'format': fmt,
                            'bitrate': bitrate,
                            'ext': fmt.get('ext', 'm4a'),
                            'filesize': fmt.get('filesize', 0)
                        })
                
                # 비트레이트가 높은 순으로 정렬
                audio_formats.sort(key=lambda x: x['bitrate'], reverse=True)
                
                # 최소 비트레이트 필터링
                if min_bitrate > 0:
                    audio_formats = [fmt for fmt in audio_formats if fmt['bitrate'] >= min_bitrate]
                
                if audio_formats:
                    best_audio = audio_formats[0]
                    return {
                        'url': best_audio['format'].get('url', ''),
                        'title': info.get('title', 'Unknown'),
                        'ext': best_audio['ext'],
                        'filesize': best_audio['filesize'],
                        'bitrate': best_audio['bitrate']
                    }
                else:
                    # 오디오 전용 포맷이 없으면 비디오+오디오 포맷에서 오디오 추출
                    for fmt in formats:
                        if (fmt.get('acodec') != 'none' and 
                            fmt.get('vcodec') != 'none' and
                            fmt.get('height') and fmt.get('height') <= 720):  # 낮은 해상도 선택
                            return {
                                'url': fmt.get('url', ''),
                                'title': info.get('title', 'Unknown'),
                                'ext': 'mp4',  # 비디오+오디오 포맷
                                'filesize': fmt.get('filesize', 0),
                                'note': '비디오+오디오 포맷 (오디오 추출 필요)'
                            }
            else:
                # 비디오 다운로드하는 경우
                if format_id:
                    for fmt in formats:
                        if fmt.get('format_id') == format_id:
                            return {
                                'url': fmt.get('url', ''),
                                'title': info.get('title', 'Unknown'),
                                'ext': fmt.get('ext', 'mp4'),
                                'filesize': fmt.get('filesize', 0)
                            }
                else:
                    # 최고 품질 선택 (오디오 포함) - 더 엄격한 필터링
                    best_format = None
                    best_score = 0
                    
                    for fmt in formats:
                        # 비디오와 오디오가 모두 있는 포맷만 선택
                        has_video = fmt.get('vcodec') != 'none' and fmt.get('height') and fmt.get('height') > 0
                        has_audio = fmt.get('acodec') != 'none'
                        
                        if has_video and has_audio:
                            # 품질 점수 계산 (해상도 + 비트레이트)
                            height = fmt.get('height', 0)
                            bitrate = fmt.get('tbr', 0) or 0
                            score = height * 1000 + bitrate  # 해상도 우선, 비트레이트 보조
                            
                            if score > best_score:
                                best_format = fmt
                                best_score = score
                    
                    if best_format:
                        return {
                            'url': best_format.get('url', ''),
                            'title': info.get('title', 'Unknown'),
                            'ext': best_format.get('ext', 'mp4'),
                            'filesize': best_format.get('filesize', 0),
                            'height': best_format.get('height', 0),
                            'acodec': best_format.get('acodec', ''),
                            'vcodec': best_format.get('vcodec', '')
                        }
        
        return None
    except Exception as e:
        st.error(f"다운로드 URL 가져오기 실패: {e}")
        return None

# AI 기능을 위한 함수들
def get_ai_response(prompt, model_name, system_prompt="", target_language=None):
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
            result = response.content if hasattr(response, 'content') else str(response)
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
            result = response.choices[0].message.content
        
        # 언어 검증 (선택적)
        if target_language and result:
            # 간단한 언어 검증 - 한국어, 영어, 중국어, 일본어 등
            if target_language == "Korean" and not any(char in result for char in ['가', '나', '다', '라', '마', '바', '사', '아', '자', '차', '카', '타', '파', '하']):
                # 한국어가 아닌 경우 재시도
                retry_prompt = f"{prompt}\n\n중요: 반드시 한국어로만 응답해주세요. 영어나 다른 언어를 사용하지 마세요."
                if model_name.startswith('claude'):
                    retry_response = client.invoke([
                        {"role": "system", "content": system_prompt + "\n\nCRITICAL: You MUST respond in Korean only."},
                        {"role": "user", "content": retry_prompt}
                    ])
                    result = retry_response.content if hasattr(retry_response, 'content') else str(retry_response)
                else:
                    retry_response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt + "\n\nCRITICAL: You MUST respond in Korean only."},
                            {"role": "user", "content": retry_prompt}
                        ],
                        max_tokens=8192,
                        temperature=0.7
                    )
                    result = retry_response.choices[0].message.content
            
            elif target_language == "English" and any(char in result for char in ['가', '나', '다', '라', '마', '바', '사', '아', '자', '차', '카', '타', '파', '하']):
                # 영어가 아닌 경우 재시도
                retry_prompt = f"{prompt}\n\nImportant: Please respond in English only. Do not use Korean or other languages."
                if model_name.startswith('claude'):
                    retry_response = client.invoke([
                        {"role": "system", "content": system_prompt + "\n\nCRITICAL: You MUST respond in English only."},
                        {"role": "user", "content": retry_prompt}
                    ])
                    result = retry_response.content if hasattr(retry_response, 'content') else str(retry_response)
                else:
                    retry_response = client.chat.completions.create(
                        model=model_name,
                        messages=[
                            {"role": "system", "content": system_prompt + "\n\nCRITICAL: You MUST respond in English only."},
                            {"role": "user", "content": retry_prompt}
                        ],
                        max_tokens=8192,
                        temperature=0.7
                    )
                    result = retry_response.choices[0].message.content
        
        return result
    except Exception as e:
        return f"오류 발생: {str(e)}"

def extract_transcript(url, force_whisper=False):
    """YouTube 영상에서 자막/스크립트 추출 (YouTube 자막 + Whisper API)"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'writesubtitles': False,
            'writeautomaticsub': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # 1. 먼저 YouTube 자막 시도
            transcript = extract_youtube_captions(info)
            
            # 2. Whisper API 사용 조건 확인
            openai_key = os.getenv('OPENAI_API_KEY')
            can_use_whisper = openai_key and openai_key.strip() != '' and openai_key != 'NA'
            
            # Whisper API 사용 조건
            use_whisper = False
            whisper_reason = ""
            
            if can_use_whisper:
                if force_whisper:
                    # 강제로 Whisper API 사용
                    use_whisper = True
                    if transcript:
                        whisper_reason = "사용자가 Whisper API 강제 사용을 선택했습니다"
                    else:
                        whisper_reason = "YouTube 자막이 없습니다"
                elif not transcript:
                    # YouTube 자막이 없으면 Whisper API 사용
                    use_whisper = True
                    whisper_reason = "YouTube 자막이 없습니다"
                else:
                    # YouTube 자막이 있으면 YouTube 자막 사용
                    st.info("✅ YouTube 자막을 사용합니다. (Whisper API는 YouTube 자막이 없을 때만 사용)")
            else:
                if not transcript:
                    st.error("❌ YouTube 자막이 없고 Whisper API를 사용할 수 없습니다. OPENAI_API_KEY를 설정해주세요.")
                    return None
                else:
                    st.info("✅ YouTube 자막을 사용합니다.")
            
            # 3. Whisper API 사용
            if use_whisper:
                if force_whisper:
                    st.info(f"🔄 {whisper_reason}. Whisper API로 상세한 스크립트를 생성합니다...")
                    st.info("⏳ 음성 분석 중입니다. 긴 영상의 경우 몇 분 정도 소요될 수 있습니다.")
                else:
                    st.info(f"🔄 {whisper_reason}. Whisper API로 음성을 분석합니다...")
                
                whisper_transcript = extract_whisper_transcript(url, info)
                if whisper_transcript:
                    if force_whisper:
                        st.success("✅ Whisper API로 상세한 스크립트 생성 완료!")
                    return whisper_transcript
                else:
                    st.warning("⚠️ Whisper API 분석에 실패했습니다.")
                    if transcript:
                        st.info("YouTube 자막을 사용합니다.")
                        return transcript
                    return None
            
            return transcript
            
    except Exception as e:
        st.error(f"자막 추출 실패: {e}")
        return None

def extract_youtube_captions(info):
    """YouTube 자막 추출"""
    try:
        # 자동 생성된 자막이 있는지 확인
        if 'automatic_captions' in info:
            for lang_code, captions in info['automatic_captions'].items():
                if lang_code in ['en', 'ko', 'ja', 'zh']:  # 영어, 한국어, 일본어, 중국어
                    for caption in captions:
                        if caption.get('ext') == 'vtt':
                            # VTT 자막 다운로드
                            caption_url = caption.get('url')
                            if caption_url:
                                response = requests.get(caption_url)
                                if response.status_code == 200:
                                    return parse_vtt_captions(response.text)
        
        # 수동 자막이 있는지 확인
        if 'subtitles' in info:
            for lang_code, captions in info['subtitles'].items():
                if lang_code in ['en', 'ko', 'ja', 'zh']:
                    for caption in captions:
                        if caption.get('ext') == 'vtt':
                            caption_url = caption.get('url')
                            if caption_url:
                                response = requests.get(caption_url)
                                if response.status_code == 200:
                                    return parse_vtt_captions(response.text)
        
        return None
    except Exception as e:
        st.error(f"YouTube 자막 추출 실패: {e}")
        return None

def extract_whisper_transcript(url, video_info):
    """Whisper API를 사용한 음성-텍스트 변환"""
    try:
        # OpenAI API 키 확인
        openai_key = os.getenv('OPENAI_API_KEY')
        if not openai_key or openai_key.strip() == '' or openai_key == 'NA':
            st.error("Whisper API 사용을 위해 OPENAI_API_KEY가 필요합니다.")
            return None
        
        # 최고 품질 오디오 URL 가져오기
        audio_url = get_best_audio_url(video_info)
        if not audio_url:
            st.error("오디오 URL을 가져올 수 없습니다.")
            return None
        
        # Whisper API 호출
        client = OpenAI(api_key=openai_key)
        
        with st.spinner("🎙️ Whisper API로 음성을 분석하는 중..."):
            # 오디오 다운로드
            audio_response = requests.get(audio_url)
            if audio_response.status_code != 200:
                st.error("오디오 파일을 다운로드할 수 없습니다.")
                return None
            
            # Whisper API 호출
            response = client.audio.transcriptions.create(
                model="whisper-1",
                file=("audio.mp3", audio_response.content, "audio/mpeg"),
                language="auto",  # 자동 언어 감지
                response_format="text"
            )
            
            return response
            
    except Exception as e:
        st.error(f"Whisper API 오류: {e}")
        return None

def get_best_audio_url(video_info):
    """최고 품질 오디오 URL 가져오기"""
    try:
        formats = video_info.get('formats', [])
        best_audio = None
        best_bitrate = 0
        
        for fmt in formats:
            # 오디오만 있는 포맷 찾기
            if (fmt.get('acodec') != 'none' and 
                (fmt.get('vcodec') == 'none' or not fmt.get('height') or fmt.get('height') == 0)):
                
                bitrate = fmt.get('abr', 0) or fmt.get('tbr', 0) or 0
                if bitrate > best_bitrate:
                    best_audio = fmt
                    best_bitrate = bitrate
        
        if best_audio:
            return best_audio.get('url')
        
        # 오디오 전용 포맷이 없으면 비디오+오디오 포맷에서 낮은 해상도 선택
        for fmt in formats:
            if (fmt.get('acodec') != 'none' and fmt.get('vcodec') != 'none' and
                fmt.get('height') and fmt.get('height') <= 720):
                return fmt.get('url')
        
        return None
    except Exception as e:
        st.error(f"오디오 URL 가져오기 실패: {e}")
        return None

def parse_vtt_captions(vtt_content):
    """VTT 자막 파일을 파싱하여 텍스트 추출"""
    try:
        lines = vtt_content.split('\n')
        transcript = []
        
        for line in lines:
            line = line.strip()
            # 타임스탬프나 빈 줄, WEBVTT 헤더는 건너뛰기
            if (line and not line.startswith('WEBVTT') and 
                not '-->' in line and not line.isdigit()):
                transcript.append(line)
        
        return ' '.join(transcript)
    except Exception as e:
        st.error(f"자막 파싱 실패: {e}")
        return None

def generate_summary_and_transcript(video_info, transcript, model_name, languages, custom_prompt="", include_keywords=True, include_quotes=True, include_timeline=False, include_action_items=False):
    """영상 요약 및 스크립트 생성"""
    try:
        # 추가 분석 옵션에 따른 프롬프트 확장
        additional_requirements = []
        
        if include_keywords:
            additional_requirements.append("- **🔑 핵심 키워드**: 영상에서 중요한 키워드들을 추출하여 정리")
        
        if include_quotes:
            additional_requirements.append("- **💬 주요 인용구**: 영상에서 중요한 인용구나 발언을 추출")
        
        if include_timeline:
            additional_requirements.append("- **⏰ 시간별 요약**: 영상의 시간대별 주요 내용을 정리")
        
        if include_action_items:
            additional_requirements.append("- **✅ 액션 아이템**: 영상에서 도출할 수 있는 실행 가능한 액션 아이템을 정리")
        
        additional_sections = "\n".join(additional_requirements) if additional_requirements else ""
        
        # 요약 프롬프트 생성
        summary_prompt = f"""
다음 YouTube 영상의 내용을 상세하고 구조화된 형태로 요약해주세요:

제목: {video_info['title']}
업로더: {video_info['uploader']}
길이: {format_duration(video_info['duration'])}
설명: {video_info['description'][:500]}...

스크립트 내용:
{transcript[:4000] if transcript else "스크립트를 사용할 수 없습니다."}

**🎯 사용자 특별 요청사항 (반드시 참고하세요):**
{custom_prompt if custom_prompt else "영상의 주요 내용을 객관적이고 중립적으로 요약해주세요."}

**중요: 위의 사용자 요청사항을 반드시 고려하여 요약을 작성해주세요. 사용자가 특별히 요청한 관점이나 분석 방향을 우선적으로 반영해주세요.**

다음 형식으로 상세하게 요약해주세요:

## 📋 영상 개요
- 영상의 전반적인 주제와 목적
- 주요 다루는 내용의 범위
- 사용자 요청사항 관점에서의 영상 가치

## 🎯 핵심 내용
1. **주요 주제**: 영상의 중심 주제 (사용자 요청사항 반영)
2. **핵심 포인트**: 중요한 내용들을 5-8개로 정리
   - 각 포인트는 구체적이고 명확하게 작성
   - 중요한 데이터, 통계, 예시 포함
   - 사용자 요청사항에 맞는 관점으로 분석
3. **세부 내용**: 주요 포인트들의 상세 설명

{additional_sections}

## 💡 주요 인사이트
- 영상에서 얻을 수 있는 중요한 교훈이나 통찰
- 실용적인 적용 가능한 내용
- 사용자 요청사항 관점에서의 특별한 인사이트

## 📝 결론 및 요약
- 영상의 핵심 메시지
- 시청자에게 남겨진 인상이나 생각할 점
- 사용자 요청사항에 따른 추가 권장사항

요약은 상세하고 가독성이 좋게 작성해주세요. 각 섹션은 명확하게 구분하고, 중요한 내용은 강조해주세요. **사용자의 요청사항을 반드시 우선적으로 반영하여 맞춤형 분석을 제공해주세요.**
"""
        
        # 스크립트 프롬프트 생성
        script_prompt = f"""
다음 YouTube 영상의 내용을 바탕으로 상세하고 구조화된 스크립트를 작성해주세요:

제목: {video_info['title']}
업로더: {video_info['uploader']}
길이: {format_duration(video_info['duration'])}

원본 스크립트:
{transcript[:4000] if transcript else "스크립트를 사용할 수 없습니다."}

**🎯 사용자 특별 요청사항 (반드시 참고하세요):**
{custom_prompt if custom_prompt else "영상의 주요 내용을 객관적이고 중립적으로 스크립트로 작성해주세요."}

**중요: 위의 사용자 요청사항을 반드시 고려하여 스크립트를 작성해주세요. 사용자가 특별히 요청한 관점이나 분석 방향을 우선적으로 반영해주세요.**

다음 형식으로 상세한 스크립트를 작성해주세요:

## 🎬 영상 스크립트

### 📖 도입부 (Introduction)
- 영상의 시작과 주제 소개
- 시청자에게 전달할 메시지의 개요
- 영상의 목적과 기대 효과
- 사용자 요청사항 관점에서의 영상 가치

### 📚 본론 (Main Content)
영상의 주요 내용을 시간순으로 상세히 정리:

1. **첫 번째 주제**
   - 구체적인 내용과 설명
   - 중요한 포인트와 예시
   - 관련 데이터나 통계
   - 사용자 요청사항에 맞는 관점으로 분석

2. **두 번째 주제**
   - 상세한 설명과 분석
   - 핵심 메시지와 인사이트
   - 실용적인 적용 방법
   - 사용자 요청사항 관점에서의 특별한 의미

3. **추가 주제들**
   - 영상에서 다루는 모든 주요 내용
   - 각 주제별 상세 설명
   - 사용자 요청사항에 따른 추가 분석

### 💡 핵심 메시지
- 영상에서 가장 중요한 메시지들
- 시청자가 기억해야 할 핵심 포인트
- 실용적인 적용 가능한 내용
- 사용자 요청사항 관점에서의 특별한 인사이트

### 🎯 결론 (Conclusion)
- 영상의 마무리와 요약
- 시청자에게 남겨진 인상
- 다음 단계나 추가 고려사항
- 사용자 요청사항에 따른 추가 권장사항

스크립트는 자연스럽고 읽기 쉬우며, 상세하고 구조화된 형태로 작성해주세요. 각 섹션은 명확하게 구분하고, 중요한 내용은 강조해주세요. **사용자의 요청사항을 반드시 우선적으로 반영하여 맞춤형 스크립트를 제공해주세요.**
"""
        
        results = {}
        
        def process_language(lang):
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
            
            target_lang = language_names.get(lang, "English")
            
            # 언어별 강력한 시스템 프롬프트 생성
            summary_system = f"""You are a professional content summarizer. 
IMPORTANT: You MUST respond ONLY in {target_lang}. 
DO NOT use any other language. 
If the target language is Korean, respond in Korean.
If the target language is English, respond in English.
If the target language is Chinese, respond in Chinese.
If the target language is Japanese, respond in Japanese.
If the target language is French, respond in French.
If the target language is German, respond in German.
If the target language is Spanish, respond in Spanish.
If the target language is Italian, respond in Italian.
If the target language is Russian, respond in Russian.
If the target language is Portuguese, respond in Portuguese.

CRITICAL: Your response must be 100% in {target_lang} language.

MOST IMPORTANT: When the user provides specific analysis requirements or custom prompts, you MUST prioritize and incorporate those requirements as the primary focus of your analysis. The user's specific requests should guide your entire response structure and content."""
            
            script_system = f"""You are a professional script writer. 
IMPORTANT: You MUST respond ONLY in {target_lang}. 
DO NOT use any other language. 
If the target language is Korean, respond in Korean.
If the target language is English, respond in English.
If the target language is Chinese, respond in Chinese.
If the target language is Japanese, respond in Japanese.
If the target language is French, respond in French.
If the target language is Italian, respond in Italian.
If the target language is Spanish, respond in Spanish.
If the target language is German, respond in German.
If the target language is Russian, respond in Russian.
If the target language is Portuguese, respond in Portuguese.

CRITICAL: Your response must be 100% in {target_lang} language.

MOST IMPORTANT: When the user provides specific analysis requirements or custom prompts, you MUST prioritize and incorporate those requirements as the primary focus of your analysis. The user's specific requests should guide your entire response structure and content."""
            
            # 언어별 프롬프트에 언어 지시 추가
            lang_specific_summary_prompt = f"""
{summary_prompt}

**LANGUAGE REQUIREMENT: You MUST respond in {target_lang} only. Do not use any other language.**

**중요: 반드시 {lang}로만 응답해주세요. 다른 언어를 사용하지 마세요.**

**FINAL REMINDER: Your entire response must be written in {target_lang}. If you see this message, ensure you are responding in {target_lang} only.**
"""
            
            lang_specific_script_prompt = f"""
{script_prompt}

**LANGUAGE REQUIREMENT: You MUST respond in {target_lang} only. Do not use any other language.**

**중요: 반드시 {lang}로만 응답해주세요. 다른 언어를 사용하지 마세요.**

**FINAL REMINDER: Your entire response must be written in {target_lang}. If you see this message, ensure you are responding in {target_lang} only.**
"""
            
            # 사용자 프롬프트가 있는 경우 강조
            if custom_prompt:
                enhanced_summary_prompt = f"{lang_specific_summary_prompt}\n\n🚨 최종 중요사항: 사용자가 요청한 특별한 분석 요구사항을 반드시 우선적으로 고려하여 응답해주세요. 사용자의 요청사항이 분석의 핵심이 되어야 합니다."
                enhanced_script_prompt = f"{lang_specific_script_prompt}\n\n🚨 최종 중요사항: 사용자가 요청한 특별한 분석 요구사항을 반드시 우선적으로 고려하여 응답해주세요. 사용자의 요청사항이 분석의 핵심이 되어야 합니다."
            else:
                enhanced_summary_prompt = lang_specific_summary_prompt
                enhanced_script_prompt = lang_specific_script_prompt
            
            # 요약 생성
            summary_result = get_ai_response(enhanced_summary_prompt, model_name, summary_system, target_language=target_lang)
            
            # 스크립트 생성
            script_result = get_ai_response(enhanced_script_prompt, model_name, script_system, target_language=target_lang)
            
            return {
                'summary': summary_result,
                'script': script_result
            }
        
        # ThreadPoolExecutor를 사용하여 동시에 처리
        with ThreadPoolExecutor(max_workers=len(languages)) as executor:
            futures = [executor.submit(process_language, lang) for lang in languages]
            
            # 진행 상황 표시
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            completed = 0
            for i, future in enumerate(futures):
                lang = languages[i]
                status_text.text(f"🌍 {lang} 분석 중...")
                
                result = future.result()
                results[lang] = result
                
                completed += 1
                progress = completed / len(languages)
                progress_bar.progress(progress)
                status_text.text(f"✅ {lang} 분석 완료! ({completed}/{len(languages)})")
            
            progress_bar.progress(1.0)
            status_text.text(f"🎉 모든 언어 분석 완료! ({len(languages)}개 언어)")
        
        return results
        
    except Exception as e:
        st.error(f"요약 및 스크립트 생성 실패: {e}")
        return None

def create_download_files(video_info, results, languages, generate_summary, generate_script):
    """다운로드용 파일 생성"""
    try:
        # 안전한 파일명 생성
        safe_title = re.sub(r'[^\w\s-]', '', video_info['title']).strip()
        safe_title = re.sub(r'[-\s]+', '-', safe_title)
        safe_title = safe_title[:50]  # 파일명 길이 제한
        
        download_files = {}
        
        # 각 언어별 파일 생성
        for lang in languages:
            lang_result = results.get(lang, {})
            
            # 요약 파일 생성
            if generate_summary and 'summary' in lang_result:
                summary_content = f"""YouTube 영상 분석 - 요약
제목: {video_info['title']}
업로더: {video_info['uploader']}
길이: {format_duration(video_info['duration'])}
분석 언어: {lang}
생성 날짜: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

{'='*50}

{lang_result['summary']}
"""
                download_files[f"{safe_title}_요약_{lang}.txt"] = summary_content
            
            # 스크립트 파일 생성
            if generate_script and 'script' in lang_result:
                script_content = f"""YouTube 영상 분석 - 스크립트
제목: {video_info['title']}
업로더: {video_info['uploader']}
길이: {format_duration(video_info['duration'])}
분석 언어: {lang}
생성 날짜: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

{'='*50}

{lang_result['script']}
"""
                download_files[f"{safe_title}_스크립트_{lang}.txt"] = script_content
        
        # 통합 파일 생성
        if len(languages) > 1:
            combined_content = f"""YouTube 영상 분석 - 통합 보고서
제목: {video_info['title']}
업로더: {video_info['uploader']}
길이: {format_duration(video_info['duration'])}
분석 언어: {', '.join(languages)}
생성 날짜: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

{'='*50}

"""
            
            for lang in languages:
                lang_result = results.get(lang, {})
                combined_content += f"\n## {lang} 분석 결과\n"
                
                if generate_summary and 'summary' in lang_result:
                    combined_content += f"\n### 📋 요약\n{lang_result['summary']}\n"
                
                if generate_script and 'script' in lang_result:
                    combined_content += f"\n### 📄 스크립트\n{lang_result['script']}\n"
                
                combined_content += "\n" + "="*50 + "\n"
            
            download_files[f"{safe_title}_통합분석.txt"] = combined_content
        
        return download_files
        
    except Exception as e:
        st.error(f"다운로드 파일 생성 실패: {e}")
        return {}

# 진행률 관련 함수는 클라이언트 다운로드에서는 불필요하므로 제거

def format_duration(seconds):
    """초를 시:분:초 형식으로 변환"""
    if not seconds:
        return "Unknown"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"

def format_file_size(bytes_size):
    """바이트를 읽기 쉬운 크기로 변환"""
    if not bytes_size:
        return "Unknown"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"

# 사이드바 설정
with st.sidebar:
    st.header("⚙️ 설정")
    
    # 동시 URL 생성 수 제한
    max_concurrent_downloads = st.slider(
        "최대 동시 URL 생성 수",
        min_value=1,
        max_value=5,
        value=2,
        help="너무 많은 동시 요청은 YouTube에서 차단할 수 있습니다"
    )

# 메인 컨텐츠
tab1, tab2, tab3 = st.tabs(["🤖 AI 분석", "🎥 단일 영상 다운로드", "📦 재생목록 다운로드"])

with tab1:
    st.header("🤖 AI 분석 - 요약 및 스크립트 생성")
    
    # 사용 목적 안내
    st.info("💡 **개인적, 교육적, 연구 목적으로만 사용해주세요.** 상업적 사용은 금지됩니다.")
    
    # AI 모델 선택
    st.subheader("🧠 AI 모델 설정")
    
    # 사용 가능한 모델 확인
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
        st.error("⚠️ API 키가 설정되지 않았습니다. ANTHROPIC_API_KEY 또는 OPENAI_API_KEY를 설정해주세요.")
        st.info("💡 API 키 설정 방법:\n"
               "- ANTHROPIC_API_KEY: Claude 모델 사용\n"
               "- OPENAI_API_KEY: GPT 모델 사용")
    else:
        selected_ai_model = st.selectbox(
            '🧠 AI 모델 선택',
            options=available_models,
            index=0,
            help='Claude는 ANTHROPIC_API_KEY, OpenAI는 OPENAI_API_KEY 필요'
        )
        
        # YouTube URL 입력
        st.subheader("📺 분석할 YouTube 영상")
        analysis_url = st.text_input(
            "YouTube URL 입력",
            placeholder="https://www.youtube.com/watch?v=...",
            help="분석할 YouTube 영상의 URL을 입력하세요"
        )
    
        if analysis_url:
            analysis_video_id = extract_video_id(analysis_url)
            if analysis_video_id:
                st.success(f"✅ 유효한 YouTube URL입니다. (비디오 ID: {analysis_video_id})")
                
                # 비디오 정보 가져오기
                with st.spinner("비디오 정보를 가져오는 중..."):
                    analysis_video_info = get_video_info(analysis_url)
                
                if analysis_video_info:
                    # 비디오 정보 표시
                    col1, col2 = st.columns([1, 2])
                    
                    with col1:
                        if analysis_video_info['thumbnail']:
                            st.image(analysis_video_info['thumbnail'], width=200)
                    
                    with col2:
                        st.subheader(analysis_video_info['title'])
                        st.write(f"**업로더:** {analysis_video_info['uploader']}")
                        st.write(f"**길이:** {format_duration(analysis_video_info['duration'])}")
                        st.write(f"**조회수:** {analysis_video_info['view_count']:,}")
                        st.write(f"**업로드 날짜:** {analysis_video_info['upload_date']}")
                    
                    # 자막 추출
                    st.subheader("📝 자막/스크립트 추출")
                    
                    # Whisper API 사용 조건 표시
                    has_openai_key = os.environ.get('OPENAI_API_KEY') is not None
                    if has_openai_key:
                        st.info("🎙️ Whisper API 사용 가능")
                        
                        # Whisper API 강제 사용 옵션
                        force_whisper = st.checkbox(
                            "🔧 Whisper API 강제 사용",
                            value=False,
                            help="YouTube 자막이 있어도 Whisper API를 사용합니다. 더 상세한 스크립트를 얻을 수 있지만 처리 시간이 오래 걸립니다."
                        )
                        
                        if force_whisper:
                            st.warning("⚠️ Whisper API를 강제로 사용합니다. 처리 시간이 오래 걸릴 수 있습니다.")
                            st.info("💡 **Whisper API 강제 사용의 장점:**")
                            st.markdown("""
                            - **더 상세한 스크립트**: 음성 인식으로 모든 내용을 포착
                            - **더 정확한 내용**: 자막이 부족한 부분도 완전히 분석
                            - **더 나은 품질**: AI 기반 음성-텍스트 변환으로 품질 향상
                            """)
                        
                        st.markdown("""
                        **Whisper API 사용 조건:**
                        - YouTube 자막이 없는 경우 자동 사용
                        - 위 옵션을 체크하면 YouTube 자막이 있어도 Whisper API 사용
                        - Whisper API는 더 상세하고 정확한 스크립트를 제공할 수 있음
                        """)
                    else:
                        st.warning("⚠️ Whisper API를 사용하려면 OPENAI_API_KEY를 설정해주세요.")
                        st.markdown("""
                        **현재 제한사항:**
                        - YouTube 자막만 사용 가능
                        - 자막이 없는 경우 분석이 제한될 수 있음
                        """)
                    
                    with st.spinner("자막을 추출하는 중..."):
                        transcript = extract_transcript(analysis_url, force_whisper=force_whisper if has_openai_key else False)
                    
                    if transcript:
                        st.success("✅ 자막을 성공적으로 추출했습니다!")
                        
                        # 자막 품질 표시 (Whisper API 사용 여부 반영)
                        if force_whisper and has_openai_key:
                            st.success("🎙️ Whisper API로 상세한 스크립트를 생성했습니다!")
                            st.info("📊 스크립트 품질: Whisper API 기반 (음성 인식으로 생성된 상세한 내용)")
                        else:
                            # 자막 길이에 따른 품질 표시
                            if len(transcript) > 500:
                                st.success("📊 자막 품질: 우수 (상세한 내용 포함)")
                            elif len(transcript) > 200:
                                st.info("📊 자막 품질: 보통 (기본 내용 포함)")
                            else:
                                st.warning("📊 자막 품질: 제한적 (Whisper API로 보완됨)")
                        
                        with st.expander("📄 원본 자막 보기"):
                            st.text_area("추출된 자막", value=transcript, height=200, disabled=True)
                    else:
                        st.error("❌ 자막을 추출할 수 없습니다. 다른 영상을 시도해보세요.")
                        transcript = None
                    
                    # 언어 선택
                    st.subheader("🌍 분석 언어 선택")
                    available_languages = [
                        "한국어", "영어", "중국어", "일본어", "프랑스어", 
                        "독일어", "스페인어", "이탈리아어", "러시아어", "포르투갈어"
                    ]
                    
                    analysis_languages = st.multiselect(
                        "요약 및 스크립트를 생성할 언어들",
                        available_languages,
                        default=["한국어", "영어"],
                        help="여러 언어를 선택할 수 있습니다"
                    )
                    
                    # 분석 옵션
                    st.subheader("⚙️ 분석 옵션")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        generate_summary = st.checkbox("📋 요약 생성", value=True, help="영상의 주요 내용을 요약합니다")
                    
                    with col2:
                        generate_script = st.checkbox("📄 스크립트 생성", value=True, help="상세한 스크립트를 생성합니다")
                    
                    # 프롬프트 설정
                    st.subheader("🎯 분석 프롬프트 설정")
                    st.info("💡 AI가 요약을 생성할 때 참고할 추가 정보나 특별한 관점을 입력하세요.")
                    
                    # 프롬프트 템플릿 선택
                    prompt_template = st.selectbox(
                        "프롬프트 템플릿 선택",
                        [
                            "기본 요약",
                            "비즈니스 분석",
                            "교육/학습 목적",
                            "기술 분석",
                            "마케팅 분석",
                            "투자/금융 분석",
                            "커스텀 프롬프트"
                        ],
                        help="분석 목적에 맞는 프롬프트 템플릿을 선택하거나 커스텀 프롬프트를 입력하세요"
                    )
                    
                    # 선택된 템플릿에 따른 기본 프롬프트 설정
                    default_prompts = {
                        "기본 요약": "영상의 주요 내용을 객관적이고 중립적으로 요약해주세요.",
                        "비즈니스 분석": "비즈니스 관점에서 영상의 핵심 인사이트, 기회요인, 위험요인, 시장 동향 등을 분석해주세요.",
                        "교육/학습 목적": "교육적 가치가 있는 내용을 중심으로 학습 포인트, 핵심 개념, 실용적 적용 방법을 정리해주세요.",
                        "기술 분석": "기술적 관점에서 영상의 기술적 내용, 혁신 요소, 기술 트렌드, 구현 방법 등을 분석해주세요.",
                        "마케팅 분석": "마케팅 관점에서 타겟 고객, 제품/서비스 특징, 경쟁 우위, 마케팅 전략 등을 분석해주세요.",
                        "투자/금융 분석": "투자/금융 관점에서 수익성, 위험도, 시장 잠재력, 재무적 의미 등을 분석해주세요.",
                        "커스텀 프롬프트": ""
                    }
                    
                    # 프롬프트 입력
                    if prompt_template == "커스텀 프롬프트":
                        custom_prompt = st.text_area(
                            "커스텀 분석 프롬프트",
                            placeholder="예시: 이 영상을 스타트업 창업자 관점에서 분석해주세요. 특히 자금 조달 방법과 초기 고객 확보 전략에 집중해서 요약해주세요.",
                            height=100,
                            help="AI가 요약을 생성할 때 참고할 특별한 관점이나 분석 요청사항을 입력하세요"
                        )
                    else:
                        custom_prompt = st.text_area(
                            "분석 프롬프트 (수정 가능)",
                            value=default_prompts[prompt_template],
                            height=100,
                            help="선택한 템플릿을 기반으로 프롬프트를 수정하거나 추가 요청사항을 입력하세요"
                        )
                    
                    # 커스텀 프롬프트가 비어있는 경우 기본값 설정
                    if not custom_prompt:
                        custom_prompt = default_prompts.get(prompt_template, "영상의 주요 내용을 객관적이고 중립적으로 요약해주세요.")
                    
                    # 추가 분석 옵션
                    st.subheader("🔍 추가 분석 옵션")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        include_keywords = st.checkbox("🔑 키워드 추출", value=True, help="영상에서 중요한 키워드들을 추출합니다")
                        include_quotes = st.checkbox("💬 주요 인용구", value=True, help="영상에서 중요한 인용구나 발언을 추출합니다")
                    
                    with col2:
                        include_timeline = st.checkbox("⏰ 시간별 요약", value=False, help="영상의 시간대별 주요 내용을 정리합니다")
                        include_action_items = st.checkbox("✅ 액션 아이템", value=False, help="영상에서 도출할 수 있는 실행 가능한 액션 아이템을 정리합니다")
                    
                    # 저장된 분석 결과가 있는지 확인
                    if st.session_state.analysis_results and st.session_state.download_files:
                        st.markdown("---")
                        st.subheader("📋 이전 분석 결과")
                        st.info("이전에 분석한 결과가 있습니다. 새로운 분석을 원하시면 아래 버튼을 클릭하세요.")
                        
                        # 이전 결과 표시
                        prev_results = st.session_state.analysis_results
                        prev_files = st.session_state.download_files
                        
                        # 다운로드 섹션
                        if prev_files:
                            st.markdown("**💾 이전 분석 파일 다운로드:**")
                            
                            # 전체 다운로드 버튼 (ZIP 파일)
                            if len(prev_files) > 1:
                                import zipfile
                                import io
                                
                                # ZIP 파일 생성
                                zip_buffer = io.BytesIO()
                                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                                    for filename, content in prev_files.items():
                                        zip_file.writestr(filename, content)
                                
                                zip_buffer.seek(0)
                                
                                # 안전한 파일명 생성
                                safe_title = re.sub(r'[^\w\s-]', '', analysis_video_info['title']).strip()
                                safe_title = re.sub(r'[-\s]+', '-', safe_title)
                                safe_title = safe_title[:50]
                                
                                st.download_button(
                                    label="📦 전체 파일 다운로드 (ZIP)",
                                    data=zip_buffer.getvalue(),
                                    file_name=f"{safe_title}_분석결과.zip",
                                    mime="application/zip",
                                    key="download_prev_all_zip"
                                )
                            
                            # 개별 파일 다운로드
                            st.markdown("**개별 파일 다운로드:**")
                            for filename, content in prev_files.items():
                                st.download_button(
                                    label=f"📥 {filename}",
                                    data=content,
                                    file_name=filename,
                                    mime="text/plain",
                                    key=f"download_prev_{filename}_{int(time.time())}"
                                )
                        
                        # 새 분석 버튼
                        if st.button("🔄 새로 분석하기", type="secondary"):
                            st.session_state.analysis_results = None
                            st.session_state.download_files = {}
                            st.rerun()
                    
                    # 분석 실행 버튼
                    if st.button("🚀 AI 분석 시작", type="primary"):
                        if not analysis_languages:
                            st.warning("분석할 언어를 최소 하나 선택해주세요.")
                            st.stop()
                        
                        if not generate_summary and not generate_script:
                            st.warning("요약 또는 스크립트 생성 중 하나를 선택해주세요.")
                            st.stop()
                        
                        # 분석 실행
                        with st.spinner("AI 분석을 진행하는 중..."):
                            start_time = time.time()
                            
                            results = generate_summary_and_transcript(
                                analysis_video_info, 
                                transcript, 
                                selected_ai_model, 
                                analysis_languages,
                                custom_prompt=custom_prompt,
                                include_keywords=include_keywords,
                                include_quotes=include_quotes,
                                include_timeline=include_timeline,
                                include_action_items=include_action_items
                            )
                            
                            end_time = time.time()
                            processing_time = round(end_time - start_time, 2)
                        
                        if results:
                            st.success(f"✅ AI 분석 완료! (처리 시간: {processing_time}초)")
                            
                            # 결과를 세션에 저장
                            st.session_state.analysis_results = results
                            
                            # 다운로드 파일 생성
                            download_files = create_download_files(
                                analysis_video_info, results, analysis_languages, 
                                generate_summary, generate_script
                            )
                            
                            # 다운로드 파일을 세션에 저장
                            st.session_state.download_files = download_files
                            
                            # 다운로드 섹션
                            if download_files:
                                st.markdown("---")
                                st.subheader("💾 파일 다운로드")
                                
                                # 전체 다운로드 버튼 (ZIP 파일)
                                if len(download_files) > 1:
                                    import zipfile
                                    import io
                                    
                                    # ZIP 파일 생성
                                    zip_buffer = io.BytesIO()
                                    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                                        for filename, content in download_files.items():
                                            zip_file.writestr(filename, content)
                                    
                                    zip_buffer.seek(0)
                                    
                                    # 안전한 파일명 생성
                                    safe_title = re.sub(r'[^\w\s-]', '', analysis_video_info['title']).strip()
                                    safe_title = re.sub(r'[-\s]+', '-', safe_title)
                                    safe_title = safe_title[:50]
                                    
                                    st.download_button(
                                        label="📦 전체 파일 다운로드 (ZIP)",
                                        data=zip_buffer.getvalue(),
                                        file_name=f"{safe_title}_분석결과.zip",
                                        mime="application/zip",
                                        key="download_all_zip"
                                    )
                                
                                # 개별 파일 다운로드
                                st.markdown("**개별 파일 다운로드:**")
                                for filename, content in download_files.items():
                                    st.download_button(
                                        label=f"📥 {filename}",
                                        data=content,
                                        file_name=filename,
                                        mime="text/plain",
                                        key=f"download_{filename}_{int(time.time())}"
                                    )
                            
                            # 결과를 탭으로 표시
                            st.markdown("---")
                            st.subheader("📊 분석 결과")
                            st.info("💡 분석 결과는 마크다운 형식으로 표시됩니다. 원본 텍스트를 보려면 아래 '원본 텍스트 보기'를 클릭하세요.")
                            
                            if len(analysis_languages) > 1:
                                tabs = st.tabs([f"🌍 {lang}" for lang in analysis_languages])
                                for i, lang in enumerate(analysis_languages):
                                    with tabs[i]:
                                        lang_result = results.get(lang, {})
                                        
                                        if generate_summary and 'summary' in lang_result:
                                            st.subheader(f"📋 {lang} 요약")
                                            # 요약을 마크다운으로 표시
                                            with st.container():
                                                st.markdown("---")
                                                # 요약 내용을 Streamlit 기본 스타일로 표시
                                                with st.container():
                                                    st.markdown(lang_result['summary'])
                                        
                                        if generate_script and 'script' in lang_result:
                                            st.subheader(f"📄 {lang} 스크립트")
                                            # 스크립트를 마크다운으로 표시
                                            with st.container():
                                                st.markdown("---")
                                                # 스크립트 내용을 Streamlit 기본 스타일로 표시
                                                with st.container():
                                                    st.markdown(lang_result['script'])
                                        
                                        # 원본 텍스트 보기 옵션
                                        with st.expander("📝 원본 텍스트 보기"):
                                            if generate_summary and 'summary' in lang_result:
                                                st.text_area(
                                                    f"{lang} 요약 (원본)",
                                                    value=lang_result['summary'],
                                                    height=200,
                                                    disabled=True
                                                )
                                            
                                            if generate_script and 'script' in lang_result:
                                                st.text_area(
                                                    f"{lang} 스크립트 (원본)",
                                                    value=lang_result['script'],
                                                    height=300,
                                                    disabled=True
                                                )
                            else:
                                # 언어가 하나면 바로 표시
                                lang = analysis_languages[0]
                                lang_result = results.get(lang, {})
                                
                                if generate_summary and 'summary' in lang_result:
                                    st.subheader(f"📋 {lang} 요약")
                                    # 요약을 마크다운으로 표시
                                    with st.container():
                                        st.markdown("---")
                                        # 요약 내용을 Streamlit 기본 스타일로 표시
                                        with st.container():
                                            st.markdown(lang_result['summary'])
                                
                                if generate_script and 'script' in lang_result:
                                    st.subheader(f"📄 {lang} 스크립트")
                                    # 스크립트를 마크다운으로 표시
                                    with st.container():
                                        st.markdown("---")
                                        # 스크립트 내용을 Streamlit 기본 스타일로 표시
                                        with st.container():
                                            st.markdown(lang_result['script'])
                                
                                # 원본 텍스트 보기 옵션
                                with st.expander("📝 원본 텍스트 보기"):
                                    if generate_summary and 'summary' in lang_result:
                                        st.text_area(
                                            f"{lang} 요약 (원본)",
                                            value=lang_result['summary'],
                                            height=200,
                                            disabled=True
                                        )
                                    
                                    if generate_script and 'script' in lang_result:
                                        st.text_area(
                                            f"{lang} 스크립트 (원본)",
                                            value=lang_result['script'],
                                            height=300,
                                            disabled=True
                                        )
                            
                            # 통계 정보
                            with st.expander("📊 분석 정보"):
                                col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                                with col_stat1:
                                    st.metric("사용 모델", selected_ai_model)
                                with col_stat2:
                                    st.metric("분석 언어 수", len(analysis_languages))
                                with col_stat3:
                                    st.metric("처리 시간", f"{processing_time}초")
                                with col_stat4:
                                    if transcript:
                                        st.metric("자막 길이", f"{len(transcript)}자")
                                    else:
                                        st.metric("영상 길이", format_duration(analysis_video_info['duration']))
                        else:
                            st.error("❌ AI 분석에 실패했습니다.")
            else:
                st.error("❌ 유효하지 않은 YouTube URL입니다.")

with tab2:
    st.header("🎥 단일 영상 다운로드")
    
    # 사용 목적 안내
    st.info("💡 **개인적, 교육적, 연구 목적으로만 사용해주세요.** 상업적 사용은 금지됩니다.")
    
    # URL 입력
    url = st.text_input(
        "YouTube URL 입력",
        placeholder="https://www.youtube.com/watch?v=...",
        help="다운로드할 YouTube 영상의 URL을 입력하세요 (개인적 사용 목적)"
    )

with tab3:
    st.header("📦 재생목록 다운로드")
    
    # 사용 목적 안내
    st.info("💡 **개인적, 교육적, 연구 목적으로만 사용해주세요.** 상업적 사용은 금지됩니다.")
    
    # 재생목록 다운로드 방법 선택
    playlist_method = st.radio(
        "재생목록 다운로드 방법",
        ["🎵 재생목록 URL", "📝 URL 목록 입력", "📄 CSV 파일 업로드"],
        help="재생목록 또는 여러 URL을 한 번에 다운로드할 수 있습니다 (개인적 사용 목적)"
    )
    
    if playlist_method == "🎵 재생목록 URL":
        playlist_url = st.text_input(
            "재생목록 URL을 입력하세요:",
            placeholder="https://www.youtube.com/playlist?list=PLAYLIST_ID"
        )
        
        if playlist_url.strip():
            if is_playlist_url(playlist_url):
                # 재생목록 정보 가져오기
                with st.spinner("재생목록 정보를 가져오는 중..."):
                    playlist_info = get_playlist_info(playlist_url)
                
                if playlist_info:
                    st.success(f"✅ 재생목록 발견: {playlist_info['title']}")
                    
                    # 재생목록 정보 표시
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("총 비디오 수", playlist_info['video_count'])
                    with col2:
                        st.metric("업로더", playlist_info['uploader'])
                    with col3:
                        total_duration = sum(video['duration'] for video in playlist_info['videos'])
                        st.metric("총 재생 시간", format_duration(total_duration))
                    
                    # 비디오 목록 표시 (처음 10개만)
                    with st.expander(f"📋 비디오 목록 보기 (총 {playlist_info['video_count']}개)"):
                        df = pd.DataFrame(playlist_info['videos'])
                        df['duration'] = df['duration'].apply(format_duration)
                        df['title'] = df['title'].str[:50] + '...'  # 제목 길이 제한
                        st.dataframe(df[['title', 'duration', 'uploader']], use_container_width=True)
                    
                    # 다운로드 옵션
                    st.markdown("---")
                    st.subheader("⚙️ 다운로드 설정")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        playlist_format = st.selectbox(
                            "포맷 선택",
                            ["최고 품질 (비디오+오디오)", "오디오만 (MP3)", "오디오만 (M4A)"],
                            key="playlist_format"
                        )
                    
                    with col2:
                        max_concurrent = st.slider("동시 다운로드 수", 1, 5, 2, key="playlist_concurrent")
                    
                    # 다운로드 범위 선택
                    col1, col2 = st.columns(2)
                    with col1:
                        download_all = st.checkbox("전체 다운로드", value=True, key="download_all_playlist")
                    
                    with col2:
                        if not download_all:
                            start_index = st.number_input("시작 번호", 1, playlist_info['video_count'], 1, key="start_index")
                            end_index = st.number_input("끝 번호", 1, playlist_info['video_count'], playlist_info['video_count'], key="end_index")
                        else:
                            start_index = 1
                            end_index = playlist_info['video_count']
                    
                    # 다운로드 미리보기
                    st.markdown("---")
                    st.subheader("📋 다운로드 미리보기")
                    
                    # 다운로드할 비디오 목록 표시
                    if download_all:
                        preview_videos = playlist_info['videos']
                    else:
                        preview_videos = playlist_info['videos'][start_index-1:end_index]
                    
                    preview_df = pd.DataFrame(preview_videos)
                    preview_df['duration'] = preview_df['duration'].apply(format_duration)
                    preview_df['title'] = preview_df['title'].str[:60] + '...'  # 제목 길이 제한
                    
                    st.dataframe(
                        preview_df[['title', 'duration', 'uploader']], 
                        use_container_width=True,
                        hide_index=True
                    )
                    
                    # 예상 파일 크기 계산 (대략적)
                    total_duration = sum(video['duration'] for video in preview_videos)
                    estimated_size = total_duration * 2  # 대략 1초당 2MB로 추정
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("다운로드할 비디오", len(preview_videos))
                    with col2:
                        st.metric("총 재생 시간", format_duration(total_duration))
                    with col3:
                        st.metric("예상 파일 크기", f"{estimated_size/1024:.1f}GB")
                    
                    # 다운로드 버튼
                    if st.button("🚀 재생목록 다운로드 시작", type="primary"):
                        # 다운로드할 비디오 선택
                        if download_all:
                            videos_to_download = playlist_info['videos']
                        else:
                            videos_to_download = playlist_info['videos'][start_index-1:end_index]
                        
                        st.info(f"📥 {len(videos_to_download)}개 비디오 다운로드를 시작합니다...")
                        
                        # 다운로드 진행 상황 표시
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        completed_downloads = 0
                        failed_downloads = []
                        
                        def download_playlist_video(video_info):
                            try:
                                url = video_info['url']
                                
                                # 포맷에 따른 다운로드 URL 생성
                                if "오디오만" in playlist_format:
                                    audio_only = True
                                    min_bitrate = 128 if "MP3" in playlist_format else 0
                                    download_info = get_download_url(url, audio_only=audio_only, min_bitrate=min_bitrate)
                                else:
                                    download_info = get_download_url(url)
                                
                                if download_info and download_info.get('url'):
                                    return True, video_info, download_info
                                else:
                                    return False, video_info, "다운로드 URL 생성 실패"
                            except Exception as e:
                                return False, video_info, str(e)
                        
                        # ThreadPoolExecutor를 사용한 병렬 다운로드
                        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
                            future_to_video = {executor.submit(download_playlist_video, video): video for video in videos_to_download}
                            
                            for future in as_completed(future_to_video):
                                success, video_info, result = future.result()
                                
                                if success:
                                    download_info = result
                                    # 다운로드 링크 생성
                                    safe_title = re.sub(r'[^\w\s-]', '', download_info['title']).strip()
                                    safe_title = re.sub(r'[-\s]+', '-', safe_title)
                                    safe_title = safe_title[:50]
                                    
                                    file_extension = download_info.get('ext', 'mp4')
                                    if "오디오만" in playlist_format:
                                        if "MP3" in playlist_format:
                                            file_extension = 'mp3'
                                        else:
                                            file_extension = 'm4a'
                                    
                                    filename = f"{safe_title}.{file_extension}"
                                    
                                    st.download_button(
                                        label=f"📥 {filename}",
                                        data=requests.get(download_info['url']).content,
                                        file_name=filename,
                                        mime=f"video/{file_extension}" if file_extension != 'mp3' else "audio/mpeg",
                                        key=f"playlist_download_{completed_downloads}_{int(time.time())}"
                                    )
                                    
                                    completed_downloads += 1
                                    

                                else:
                                    failed_downloads.append((video_info['title'], result))
                                
                                # 진행 상황 업데이트
                                progress = (completed_downloads + len(failed_downloads)) / len(videos_to_download)
                                progress_bar.progress(progress)
                                status_text.text(f"완료: {completed_downloads}/{len(videos_to_download)} (실패: {len(failed_downloads)})")
                        
                        # 완료 메시지
                        if completed_downloads > 0:
                            st.success(f"✅ {completed_downloads}개 다운로드 완료!")
                            
                            # 전체 재생목록 ZIP 다운로드 옵션 추가
                            if completed_downloads > 1:
                                st.markdown("---")
                                st.subheader("📦 전체 재생목록 다운로드")
                                st.info("모든 비디오를 ZIP 파일로 한 번에 다운로드할 수 있습니다.")
                                
                                # ZIP 파일 생성
                                import zipfile
                                import io
                                
                                zip_buffer = io.BytesIO()
                                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                                    # 성공한 다운로드들만 ZIP에 추가
                                    successful_downloads = []
                                    for future in as_completed(future_to_video):
                                        success, video_info, result = future.result()
                                        if success:
                                            download_info = result
                                            try:
                                                # 파일 내용 가져오기
                                                file_content = requests.get(download_info['url']).content
                                                
                                                # 파일명 생성
                                                safe_title = re.sub(r'[^\w\s-]', '', download_info['title']).strip()
                                                safe_title = re.sub(r'[-\s]+', '-', safe_title)
                                                safe_title = safe_title[:50]
                                                
                                                file_extension = download_info.get('ext', 'mp4')
                                                if "오디오만" in playlist_format:
                                                    if "MP3" in playlist_format:
                                                        file_extension = 'mp3'
                                                    else:
                                                        file_extension = 'm4a'
                                                
                                                filename = f"{safe_title}.{file_extension}"
                                                
                                                # ZIP에 파일 추가
                                                zip_file.writestr(filename, file_content)
                                                successful_downloads.append(filename)
                                                
                                            except Exception as e:
                                                st.warning(f"ZIP 생성 중 오류: {filename} - {e}")
                                
                                zip_buffer.seek(0)
                                
                                # 안전한 재생목록 이름 생성
                                safe_playlist_title = re.sub(r'[^\w\s-]', '', playlist_info['title']).strip()
                                safe_playlist_title = re.sub(r'[-\s]+', '-', safe_playlist_title)
                                safe_playlist_title = safe_playlist_title[:50]
                                
                                # ZIP 다운로드 버튼
                                st.download_button(
                                    label=f"📦 전체 재생목록 다운로드 ({len(successful_downloads)}개 파일)",
                                    data=zip_buffer.getvalue(),
                                    file_name=f"{safe_playlist_title}_재생목록.zip",
                                    mime="application/zip",
                                    key=f"playlist_zip_{int(time.time())}"
                                )
                                
                                st.info(f"💡 ZIP 파일에는 {len(successful_downloads)}개의 파일이 포함되어 있습니다.")
                        
                        if failed_downloads:
                            st.error(f"❌ {len(failed_downloads)}개 다운로드 실패:")
                            for title, error in failed_downloads:
                                st.write(f"  - {title}: {error}")
                else:
                    st.error("❌ 재생목록 정보를 가져올 수 없습니다.")
            else:
                st.error("❌ 올바른 재생목록 URL을 입력해주세요.")
                st.info("💡 재생목록 URL 예시: https://www.youtube.com/playlist?list=PLAYLIST_ID")
    
    elif playlist_method == "📝 URL 목록 입력":
        urls_text = st.text_area(
            "YouTube URL 목록 (한 줄에 하나씩)",
            height=200,
            placeholder="https://www.youtube.com/watch?v=...\nhttps://www.youtube.com/watch?v=...\nhttps://www.youtube.com/watch?v=...",
            help="다운로드할 YouTube URL들을 한 줄에 하나씩 입력하세요"
        )
        
        if urls_text:
            urls = [url.strip() for url in urls_text.split('\n') if url.strip()]
            st.info(f"총 {len(urls)}개의 URL이 입력되었습니다.")
            
            # URL 유효성 검사
            valid_urls = []
            invalid_urls = []
            
            for url in urls:
                if extract_video_id(url):
                    valid_urls.append(url)
                else:
                    invalid_urls.append(url)
            
            if invalid_urls:
                st.warning(f"유효하지 않은 URL {len(invalid_urls)}개:")
                for url in invalid_urls:
                    st.write(f"❌ {url}")
            
            if valid_urls:
                st.success(f"유효한 URL {len(valid_urls)}개:")
                for url in valid_urls:
                    st.write(f"✅ {url}")
                
                # 그룹 다운로드 옵션
                st.markdown("---")
                st.subheader("📥 그룹 다운로드 옵션")
                
                group_format_type = st.radio(
                    "다운로드 타입",
                    ["🎬 영상 + 음성", "🎵 음성만 (오디오)"],
                    key="group_format"
                )
                
                # 동시 다운로드 설정
                concurrent_downloads = st.slider(
                    "동시 다운로드 수",
                    min_value=1,
                    max_value=len(valid_urls),
                    value=min(2, len(valid_urls)),
                    help="너무 많은 동시 다운로드는 YouTube에서 차단할 수 있습니다"
                )
                
                # 그룹 다운로드 버튼
                if st.button("🚀 그룹 다운로드 URL 생성", type="primary"):
                    # 다운로드 옵션 설정
                    if group_format_type == "🎵 음성만 (오디오)":
                        audio_only = True
                    else:
                        audio_only = False
                    
                    # URL 생성 진행률 표시
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    completed = 0
                    failed = 0
                    download_links = []
                    
                    def generate_download_url(url):
                        try:
                            # 비디오 정보 가져오기
                            video_info = get_video_info(url)
                            if not video_info:
                                return False, url, "비디오 정보 가져오기 실패", None
                            
                            # 다운로드 URL 가져오기
                            download_info = get_download_url(url, format_id='best', audio_only=audio_only)
                            if not download_info:
                                return False, url, "다운로드 URL 생성 실패", None
                            
                            # 파일명 생성
                            safe_title = re.sub(r'[^\w\s-]', '', video_info['title']).strip()
                            safe_title = re.sub(r'[-\s]+', '-', safe_title)
                            safe_title = safe_title[:50]  # 파일명 길이 제한
                            
                            # 파일 확장자 설정
                            if audio_only:
                                file_ext = download_info.get('ext', 'm4a')
                            else:
                                file_ext = download_info.get('ext', 'mp4')
                            
                            # 다운로드 링크 정보
                            link_info = {
                                'title': video_info['title'],
                                'url': download_info['url'],
                                'filename': f"{safe_title}.{file_ext}",
                                'filesize': download_info.get('filesize', 0),
                                'format': group_format_type,
                                'height': download_info.get('height', 0),
                                'acodec': download_info.get('acodec', ''),
                                'vcodec': download_info.get('vcodec', '')
                            }
                            

                            
                            return True, url, video_info['title'], link_info
                                
                        except Exception as e:
                            return False, url, str(e), None
                    
                    # ThreadPoolExecutor를 사용한 동시 URL 생성
                    with ThreadPoolExecutor(max_workers=concurrent_downloads) as executor:
                        future_to_url = {executor.submit(generate_download_url, url): url for url in valid_urls}
                        
                        for future in as_completed(future_to_url):
                            success, url, result, link_info = future.result()
                            
                            if success:
                                completed += 1
                                download_links.append(link_info)
                                st.success(f"✅ {result}")
                            else:
                                failed += 1
                                st.error(f"❌ {url}: {result}")
                            
                            # 진행률 업데이트
                            total = len(valid_urls)
                            progress = (completed + failed) / total
                            progress_bar.progress(progress)
                            status_text.text(f"진행률: {completed + failed}/{total} (성공: {completed}, 실패: {failed})")
                    
                    # 다운로드 링크 표시
                    if download_links:
                        st.markdown("---")
                        st.subheader("📥 다운로드 링크")
                        st.success(f"🎉 {len(download_links)}개의 다운로드 링크가 생성되었습니다!")
                        
                        # 각 링크별 다운로드 버튼 생성
                        for i, link_info in enumerate(download_links, 1):
                            size_info = f" ({format_file_size(link_info['filesize'])})" if link_info['filesize'] else ""
                            
                            col1, col2 = st.columns([3, 1])
                            
                            with col1:
                                if group_format_type == "🎬 영상 + 음성":
                                    height = link_info.get('height', 0)
                                    format_info = f" - {height}p (비디오+오디오)" if height else ""
                                    st.write(f"**{i}. {link_info['title']}**{size_info}{format_info}")
                                else:
                                    st.write(f"**{i}. {link_info['title']}**{size_info}")
                            
                            with col2:
                                # HTML 다운로드 링크
                                download_html = f"""
                                <a href="{link_info['url']}" download="{link_info['filename']}" 
                                   style="display: inline-block; background-color: #4CAF50; color: white; 
                                          padding: 5px 10px; text-decoration: none; border-radius: 3px; 
                                          font-size: 12px; font-weight: bold;">
                                   💾 다운로드
                                </a>
                                """
                                st.markdown(download_html, unsafe_allow_html=True)
                            
                            st.write("---")
                        
                        # 일괄 다운로드 안내
                        st.info("💡 **일괄 다운로드 팁:**\n"
                               "- 각 링크를 순서대로 클릭하여 다운로드하세요.\n"
                               "- 브라우저에서 다운로드 폴더를 확인하세요.\n"
                               "- 큰 파일의 경우 다운로드에 시간이 걸릴 수 있습니다.")
                    
                    # 최종 결과
                    st.markdown("---")
                    if completed > 0:
                        st.success(f"🎉 그룹 다운로드 URL 생성 완료! 성공: {completed}개, 실패: {failed}개")
                    if failed > 0:
                        st.error(f"❌ {failed}개의 URL 생성이 실패했습니다.")
    
    else:  # CSV 파일 업로드
        uploaded_file = st.file_uploader(
            "CSV 파일 업로드",
            type=['csv'],
            help="URL 목록이 포함된 CSV 파일을 업로드하세요. 'url' 컬럼이 있어야 합니다."
        )
        
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                
                if 'url' in df.columns:
                    urls = df['url'].dropna().tolist()
                    st.success(f"CSV 파일에서 {len(urls)}개의 URL을 읽었습니다.")
                    
                    # URL 목록 표시
                    st.write("**읽어들인 URL 목록:**")
                    for i, url in enumerate(urls, 1):
                        st.write(f"{i}. {url}")
                    
                    # 여기서 위와 동일한 그룹 다운로드 로직 적용
                    # (코드 중복을 피하기 위해 함수로 분리하는 것이 좋습니다)
                    
                else:
                    st.error("CSV 파일에 'url' 컬럼이 없습니다.")
                    st.write("**필요한 CSV 형식:**")
                    st.code("url\nhttps://www.youtube.com/watch?v=...\nhttps://www.youtube.com/watch?v=...")
                    
            except Exception as e:
                st.error(f"CSV 파일 읽기 실패: {e}")

# 푸터
st.markdown("---")

# 법적 면책 조항
with st.expander("⚠️ 중요: 법적 면책 조항 및 사용 제한", expanded=False):
    st.warning("""
    **🚨 법적 면책 조항 및 사용 제한**
    
    이 애플리케이션은 **개인적, 교육적, 연구 목적으로만** 사용되어야 합니다.
    
    **❌ 금지된 사용:**
    - 상업적 목적 (수익 창출, 비즈니스 활동)
    - 저작권 침해
    - 타인의 지적 재산권 침해
    - 불법적인 콘텐츠 배포
    - YouTube 서비스 약관 위반
    
    **✅ 허용된 사용:**
    - 개인 학습 및 연구
    - 교육 목적 (비상업적)
    - 개인 소장용 콘텐츠
    - 공정 이용 범위 내 사용
    
    **📋 사용자 책임:**
    - 사용자는 관련 법률 및 YouTube 서비스 약관을 준수할 책임이 있습니다
    - 저작권 및 지적 재산권을 존중해야 합니다
    - 다운로드한 콘텐츠의 사용에 대한 모든 법적 책임은 사용자에게 있습니다
    
    **🔒 면책 조항:**
    - 이 도구의 개발자는 사용자의 행위에 대한 법적 책임을 지지 않습니다
    - 사용자는 자신의 행위에 대한 모든 법적 결과를 감수해야 합니다
    - 이 도구는 "있는 그대로" 제공되며, 어떠한 보증도 제공하지 않습니다
    
    **💡 권장사항:**
    - 저작권 보호 콘텐츠는 다운로드하지 마세요
    - 공정 이용 원칙을 준수하세요
    - 콘텐츠 제작자의 권리를 존중하세요
    """)

st.markdown("""
<div style='text-align: center; color: #666;'>
    <p>🎥 YouTube 다운로드 & AI 분석 도구</p>
    <p>💡 클라이언트 브라우저에서 직접 다운로드됩니다.</p>
    <p>🤖 Whisper API로 정확한 음성-텍스트 변환을 지원합니다.</p>
    <p>⚠️ <strong>법적 면책 조항:</strong> 이 도구는 개인적, 교육적, 연구 목적으로만 사용되어야 합니다.</p>
    <p>🚨 <strong>상업적 사용 금지:</strong> 저작권 및 YouTube 서비스 약관을 준수하세요.</p>
    <p>📋 <strong>사용자 책임:</strong> 모든 법적 책임은 사용자에게 있습니다.</p>
</div>
""", unsafe_allow_html=True) 