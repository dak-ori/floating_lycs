# floating_lycs

Windows에서 **Apple Music** 재생 정보를 읽어 **Lyrs** 앱의 tuna-obs 엔드포인트(`localhost:1608`)로 전달하는 백그라운드 브릿지 프로그램입니다.

## 동작 방식

1. Windows SMTC(System Media Transport Controls) API를 통해 Apple Music 재생 정보를 1초마다 폴링
2. 트랙 제목, 아티스트, 재생 상태, 재생 위치, 앨범 아트 변경 감지
3. 변경 사항 발생 시 Lyrs tuna-obs 프로토콜 형식으로 `http://localhost:1608/` 에 POST
4. 시스템 트레이 아이콘으로 백그라운드에서 동작

## 사전 요구사항

- **운영체제**: Windows (WinRT API 사용)
- **Python**: 3.10 이상 (`dict | None` 타입 힌트 문법 사용)
- **Apple Music**: Microsoft Store 버전 설치 및 실행
- **Lyrs**: 실행 중이어야 POST 수신 가능 (실행되지 않아도 앱은 동작함)

## 설치

```bash
pip install -r requirements.txt
```

## 실행

```bash
python main.py
```

- 시스템 트레이에 음표 아이콘이 생성됩니다.
- 종료하려면 트레이 아이콘 우클릭 → **Quit** 선택

## 개별 모듈 테스트

SMTC 읽기 기능만 단독으로 테스트할 수 있습니다 (Lyrs 없이도 동작):

```bash
python smtc_reader.py
```

Apple Music이 실행 중인 상태에서 실행하면 1초 간격으로 5회 트랙 정보를 출력합니다.

## 파일 구조

```
floating_lycs/
├── main.py          # 진입점 - 트레이 아이콘 및 브릿지 루프 관리
├── smtc_reader.py   # Windows SMTC API로 Apple Music 정보 읽기
├── lyrs_poster.py   # Lyrs tuna-obs 엔드포인트에 HTTP POST
├── requirements.txt # 의존성 패키지 목록
└── docs/
    └── spec.md      # 상세 기술 명세
```

## 설정값 (하드코딩)

변경이 필요한 경우 각 파일에서 직접 수정하세요:

| 설정 | 값 | 파일 |
|------|----|------|
| 폴링 주기 | `1.0`초 | `main.py` |
| Lyrs 엔드포인트 | `http://localhost:1608/` | `lyrs_poster.py` |
| Apple Music App ID | `AppleInc.AppleMusicWin_nzyj5cx40ttqa!App` | `smtc_reader.py` |
| POST 타임아웃 | `2`초 | `lyrs_poster.py` |
| 썸네일 버퍼 크기 | `5MB` | `smtc_reader.py` |

## 의존성

| 패키지 | 용도 |
|--------|------|
| `winrt-runtime` | WinRT 기반 런타임 |
| `winrt-Windows.Media.Control` | SMTC API 바인딩 |
| `winrt-Windows.Storage.Streams` | 앨범 아트 스트림 처리 |
| `requests` | HTTP POST 전송 |
| `pystray` | 시스템 트레이 아이콘 |
| `Pillow` | 트레이 아이콘 이미지 생성 |
