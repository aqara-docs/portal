# Google Drive API 설정 가이드

## 📋 개요
Google Meet 회의록 분석 앱에서 Google Meet의 AI 요약 기능이 자동으로 생성한 회의록 폴더에 접근하기 위해 Google Drive API를 설정해야 합니다.

## 🔧 설정 단계

### 1. Google Cloud Console에서 프로젝트 생성

1. [Google Cloud Console](https://console.cloud.google.com/)에 접속
2. 새 프로젝트 생성 또는 기존 프로젝트 선택
3. 프로젝트 이름을 기억해두세요 (예: "meet-recordings-analyzer")

### 2. Google Drive API 활성화

1. Google Cloud Console에서 "API 및 서비스" → "라이브러리" 선택
2. 검색창에 "Google Drive API" 입력
3. Google Drive API 선택 후 "사용" 버튼 클릭

### 3. OAuth 2.0 클라이언트 ID 생성

1. "API 및 서비스" → "사용자 인증 정보" 선택
2. "사용자 인증 정보 만들기" → "OAuth 클라이언트 ID" 선택
3. **⚠️ 중요**: 애플리케이션 유형에서 **"웹 애플리케이션"**을 선택해야 합니다
4. 이름 입력 (예: "Meet Recordings Analyzer")
5. **승인된 리디렉션 URI**에 다음을 추가:
   - `https://aqaranewbiz.ngrok.app`
   - `https://aqaranewbiz.ngrok.app/`
   - `http://localhost:8501` (로컬 개발용)
6. "만들기" 버튼 클릭

**🚨 주의**: Streamlit은 웹 애플리케이션이므로 "웹 애플리케이션"을 선택해야 합니다.

### 4. credentials.json 파일 다운로드

1. 생성된 OAuth 2.0 클라이언트 ID 옆의 다운로드 버튼 클릭
2. 다운로드된 JSON 파일을 `credentials.json`으로 이름 변경
3. 프로젝트 루트 디렉토리에 저장

### 5. 필요한 Python 라이브러리 설치

```bash
pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

## 🚀 사용 방법

### 첫 번째 실행 시

1. 앱을 실행하면 브라우저가 자동으로 열립니다
2. Google 계정으로 로그인
3. 앱에 Google Drive 접근 권한을 허용
4. 인증이 완료되면 `token.pickle` 파일이 생성됩니다

### 이후 실행

- `token.pickle` 파일이 있으면 자동으로 인증됩니다
- 토큰이 만료되면 자동으로 갱신됩니다

## 📁 Google Meet 폴더 구조

Google Meet의 AI 요약 기능이 자동으로 생성하는 폴더를 사용합니다:

```
Google Drive/
├── Meet Recordings/          # 영어
├── Meet 녹화/               # 한국어
├── Meet recordings/          # 영어 (소문자)
├── Google Meet Recordings/   # 전체 이름
└── ...
```

**⚠️ 중요**: 폴더를 직접 생성하지 마세요. Google Meet가 자동으로 생성합니다.

## 🔒 보안 주의사항

1. `credentials.json` 파일을 Git에 커밋하지 마세요
2. `.gitignore`에 다음 항목을 추가하세요:
   ```
   credentials.json
   token.pickle
   ```

## 🛠️ 문제 해결

### 라이브러리 설치 오류
```bash
pip install --upgrade google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### OAuth 클라이언트 타입 오류
**오류 메시지**: `Client secrets must be for a web or installed app`

**해결 방법**:
1. Google Cloud Console → API 및 서비스 → 사용자 인증 정보
2. 기존 OAuth 2.0 클라이언트 ID 삭제
3. 새로 생성할 때 **"웹 애플리케이션"** 선택
4. 승인된 리디렉션 URI에 `http://localhost:8501` 추가
5. credentials.json 파일 다시 다운로드
6. 기존 token.pickle 파일 삭제 후 재실행

### 인증 오류
1. `token.pickle` 파일 삭제
2. 앱 재실행하여 재인증

### 폴더를 찾을 수 없는 경우
1. Google Meet에서 AI 요약 기능을 사용했는지 확인
2. Google Drive에 회의록 폴더가 자동 생성되었는지 확인
3. 폴더에 접근 권한이 있는지 확인
4. 폴더명이 다음 중 하나인지 확인:
   - Meet Recordings
   - Meet 녹화
   - Meet recordings
   - Google Meet Recordings

## 📝 지원 파일 형식

- `.txt` 파일
- `.md` 파일

## 🔄 백업 옵션

Google Drive API 설정이 어려운 경우, 로컬 파일 시스템을 사용할 수 있습니다:

1. 로컬에 Google Meet 폴더와 동일한 이름의 폴더 생성
2. 회의록 파일들을 해당 폴더에 저장
3. 앱이 자동으로 로컬 폴더를 사용합니다

## 📞 추가 지원

문제가 발생하면 다음을 확인하세요:
1. Google Cloud Console에서 API가 활성화되어 있는지
2. OAuth 클라이언트 ID가 올바르게 생성되었는지
3. `credentials.json` 파일이 프로젝트 루트에 있는지
4. 필요한 Python 라이브러리가 설치되어 있는지
5. Google Meet에서 AI 요약 기능을 사용했는지 