# 출판사 정산 자동화 (Publisher Settlement Automation)

매월 진행하는 출판사 정산 업무를 Playwright 브라우저 자동화로 처리하는 Python 스크립트입니다.
Google Cloud 설정 없이, 브라우저에 로그인된 Google 계정을 그대로 사용합니다.

## 자동화 워크플로우

1. **Bookips 시트** Pivot 탭에 연도/시작일/종료일 자동 입력
2. BigQuery 데이터 커넥터 **전체 새로고침**
3. 지정한 출판사의 데이터 추출 (isbn, bookName, 사용자 수, 단가, 금액)
4. **MG Summary 시트**에서 해당 출판사의 지난달 시트를 복사
5. 새 탭 생성 (예: `26.03 개념원리`) 후 데이터 붙여넣기

## 설치

```bash
pip3 install -r requirements.txt
python3 -m playwright install chromium
```

## 사용법

```bash
# 기본 실행 (예: 2026년 3월 개념원리 정산)
python3 main.py -p 개념원리 -m 3 -y 2026

# 연도 생략 시 현재 연도 사용
python3 main.py -p 개념원리 -m 3

# 데이터만 확인 (실제 쓰기 없음)
python3 main.py -p 개념원리 -m 3 --dry-run

# BigQuery 새로고침 건너뛰기
python3 main.py -p 개념원리 -m 3 --skip-refresh
```

### 첫 실행 시

브라우저가 열리면 **Google 계정에 로그인**해주세요. 로그인 정보가 `browser_data/` 폴더에 저장되어 이후에는 자동 로그인됩니다.

## 파일 구조

```
book_auto/
├── main.py           # CLI 진입점 + 브라우저 실행
├── bookips.py        # Bookips 시트 조작 (Pivot 설정, 데이터 추출)
├── mg_summary.py     # MG Summary 시트 조작 (탭 복사, 데이터 붙여넣기)
├── config.py         # 설정 (시트 URL)
└── requirements.txt  # Python 의존성
```
