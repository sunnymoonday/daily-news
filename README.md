# 오늘의 주요기사

경제 · 시사 · 부동산 · 정부정책 네 분야의 주요기사를 한 화면에서 보는 페이지입니다.

- 페이지: https://sunnymoonday.github.io/daily-news/
- **매시간 자동 갱신**: GitHub Actions(`.github/workflows/update-news.yml`)가 매시 5분에 `scripts/fetch_news.py`를 실행해 `news.json`을 새로 만들고 Pages에 배포합니다.
- 출처: 연합뉴스·한국경제·매일경제 RSS, 정책브리핑 정책뉴스 목록
- 바로 갱신하려면 Actions 탭의 **Update news → Run workflow**를 누르거나 `gh workflow run update-news.yml`을 실행하세요.
