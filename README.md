# Apple Music → Lyrs Bridge

Lyrs가 Windows용 Apple Music(Microsoft Store)을 인식하지 못하는 문제를 해결하기 위해 만든 브릿지 프로그램입니다.  
Windows SMTC API로 Apple Music 재생 정보를 읽어 Lyrs의 tuna-obs 서버로 전달합니다.

---

## 기능

- **실시간 재생 정보 전달** — 곡 제목, 아티스트, 재생 시간을 Lyrs로 전송
- **재생 위치 보간** — SMTC가 스냅샷 방식이라 생기는 가사 튀는 현상 방지
- **앨범 커버 자동 조회** — iTunes Search API로 고해상도(600×600) 앨범 이미지 가져오기
- **시스템 트레이 상주** — 백그라운드 실행, 트레이 아이콘으로 종료

---

## 요구 사항

- Windows 10 이상
- [Lyrs](https://github.com/lyrsdev/lyrs) 실행 중 (tuna-obs 서버 활성화 필요)
- Apple Music (Microsoft Store 버전) 실행 중

---

## 설치 및 실행

### 방법 1 — 실행 파일 (권장)

[Releases](../../releases)에서 `AppleMusicLyrs.exe` 다운로드 후 실행

### 방법 2 — 소스 실행

```bash
pip install winrt-runtime winrt-Windows.Media.Control winrt-Windows.Storage.Streams
pip install pystray pillow certifi   # 선택 사항 (트레이 아이콘용)

python bridge.py
```

---

## 사용법

1. Lyrs 실행 → 설정에서 **tuna-obs 서버 활성화**
2. Apple Music 실행
3. `AppleMusicLyrs.exe` 실행
4. 음악 재생 시 Lyrs에서 가사 자동 동기화

> 종료: 시스템 트레이 아이콘 우클릭 → 종료

---

## 빌드

```bash
pip install pyinstaller certifi
pyinstaller AppleMusicLyrs.spec
# 결과물: dist/AppleMusicLyrs.exe
```
