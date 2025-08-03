# Google Service Account Key 설정 가이드

## ⚠️ 중요: OAuth 클라이언트 ID vs 서비스 계정 키

### **OAuth 클라이언트 ID** (현재 가지고 있는 파일)
- **용도**: 웹 애플리케이션의 사용자 인증
- **형식**: `{"web": {"client_id": "...", "client_secret": "..."}}`
- **특징**: 매번 사용자 인증 필요

### **서비스 계정 키** (필요한 파일)
- **용도**: 서버 간 인증 (매번 인증 불필요)
- **형식**: `{"type": "service_account", "client_email": "...", "private_key": "..."}`
- **특징**: 한 번 설정하면 계속 사용 가능

## 🚀 서비스 계정 키 생성 (권장)

### 1단계: Google Cloud Console에서 서비스 계정 생성

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 프로젝트 선택 또는 새 프로젝트 생성
3. **IAM 및 관리** → **서비스 계정** 선택
4. **서비스 계정 만들기** 클릭
5. 서비스 계정 이름 입력 (예: "meet-recordings-analyzer")
6. **만들고 계속하기** 클릭
7. **역할 선택** → **편집자** 선택
8. **완료** 클릭

### 2단계: JSON 키 파일 다운로드

1. 생성된 서비스 계정 클릭
2. **키** 탭 선택
3. **키 추가** → **새 키 만들기** 클릭
4. **JSON** 선택 후 **만들기** 클릭
5. JSON 파일이 자동으로 다운로드됨

### 3단계: 환경 변수 설정

1. 다운로드한 JSON 파일을 프로젝트 루트에 복사
2. `.env` 파일에 다음 추가:
   ```
   SERVICE_ACCOUNT_FILE=/Users/aqaralife/Documents/GitHub/portal/your-service-account-key.json
   ```
   (실제 파일 경로로 수정)

### 4단계: Google Drive API 활성화

1. **API 및 서비스** → **라이브러리** 선택
2. "Google Drive API" 검색
3. **Google Drive API** 선택 후 **사용** 클릭

## ✅ 완료!

이제 앱을 실행하면 서비스 계정 키를 사용하여 Google Drive에 자동으로 연결됩니다. 매번 인증할 필요가 없습니다!

## 🔧 문제 해결

### JSON 파일 경로 확인
```bash
ls -la /Users/aqaralife/Documents/GitHub/portal/*.json
```

### 환경변수 확인
```bash
echo $SERVICE_ACCOUNT_FILE
```

### 파일 권한 확인
```bash
chmod 600 /Users/aqaralife/Documents/GitHub/portal/your-service-account-key.json
```

## 💡 장점

- ✅ **매번 인증 불필요**: 한 번 설정하면 계속 사용
- ✅ **자동 연결**: 앱 시작 시 자동으로 Google Drive 연결
- ✅ **보안**: 서비스 계정은 특정 권한만 가짐
- ✅ **안정성**: OAuth 토큰 만료 문제 없음 