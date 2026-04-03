# 출판사 정산 자동화 (Publisher Settlement Automation)

매월 진행하는 출판사 정산 업무를 자동화하는 Python 스크립트입니다.

## 자동화 워크플로우

1. **Bookips 시트** Pivot 탭에 연도/시작일/종료일 설정
2. BigQuery 데이터 커넥터 **전체 새로고침**
3. 지정한 출판사의 데이터 추출 (isbn, bookName, 사용자 수, 단가, 금액)
4. **MG Summary 시트**에서 해당 출판사의 지난달 시트를 복사
5. 새 탭 생성 (예: `26.03 개념원리`) 후 데이터 붙여넣기

## 사전 준비

### 1. Google Cloud 프로젝트 설정

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성 또는 기존 프로젝트 선택
3. **Google Sheets API** 와 **Google Drive API** 활성화
4. **사용자 인증 정보** > **OAuth 2.0 클라이언트 ID** 생성 (데스크톱 앱)
5. `credentials.json` 다운로드 후 이 폴더에 저장

### 2. Python 환경 설정

```bash
pip install -r requirements.txt
```

## 사용법

```bash
# 기본 실행 (예: 2026년 3월 개념원리 정산)
python main.py --publisher 개념원리 --month 3 --year 2026

# 축약형
python main.py -p 개념원리 -m 3 -y 2026

# 연도 생략 시 현재 연도 사용
python main.py -p 개념원리 -m 3

# 데이터만 확인 (실제 쓰기 없음)
python main.py -p 개념원리 -m 3 --dry-run

# BigQuery 새로고침 건너뛰기 (이미 새로고침한 경우)
python main.py -p 개념원리 -m 3 --skip-refresh
```

### 첫 실행 시

브라우저가 열리며 Google 계정 인증을 요청합니다. 인증 완료 후 `token.json`이 자동 생성되어 이후에는 자동 인증됩니다.

## 파일 구조

```
book_auto/
├── main.py           # CLI 진입점
├── auth.py           # Google OAuth 2.0 인증
├── bookips.py        # Bookips 시트 데이터 추출
├── mg_summary.py     # MG Summary 시트 관리
├── config.py         # 설정 (시트 ID, 인증 경로)
├── requirements.txt  # Python 의존성
└── credentials.json  # (직접 다운로드 필요, git 제외)
```
