# Apple Music → Lyrs Bridge

## 목표
Windows Apple Music 재생 정보를 읽어서
Lyrs의 tuna-obs 플러그인이 수신하는 localhost:1608로
POST해주는 백그라운드 브릿지 프로그램
(OBS 불필요, Lyrs만 실행되어 있으면 됨)

## 동작 방식
1. PyWinRT SMTC API로 전체 세션 순회
2. Apple Music 세션(App ID 고정)을 찾아 1초 간격 폴링
3. 곡/상태 변화 감지 시 localhost:1608에 POST
4. 트레이 아이콘으로 백그라운드 상주

## Apple Music 세션 식별
- App User Model ID: `AppleInc.AppleMusicWin_nzyj5cx40ttqa!App`
- get_current_session() 사용 금지
- get_sessions()로 전체 순회 후 source_app_user_model_id로 필터링
- 못 찾으면 1초 후 재시도 (조용히 대기)

## 썸네일 추출 순서 (반드시 이 순서로)
IRandomAccessStreamReference
→ open_read_async()
→ Buffer(5MB)
→ read_async(buf, buf.capacity, InputStreamOptions.READ_AHEAD)
→ DataReader.from_buffer(buf)
→ bytearray(buf.length)
→ reader.read_bytes(img_bytes)
→ base64.b64encode(img_bytes)
→ "data:image/png;base64,{b64}"

## 재생 위치 변환
session.get_timeline_properties().position → TimeSpan (단위: 100ns)
ms 변환: int(position.total_seconds() * 1000)
duration도 동일

## POST 스펙 (tuna-obs 프로토콜)
POST http://localhost:1608/
Content-Type: application/json

{`
  "cover": "data:image/png;base64,<str>",  # 없으면 빈 문자열
  "title": "노래 제목",
  "artists": "아티스트",
  "status": "playing" | "paused" | "stopped",
  "progress": <int ms>,
  "duration": <int ms>
}

## 에러 처리
- Apple Music 꺼져 있음 → 조용히 1초 대기 후 재시도
- localhost:1608 POST 실패 → 로그만 출력, 무시 (Lyrs가 꺼져있을 수 있음)
- 썸네일 없음 → cover를 빈 문자열로 전송

## 패키지 (winsdk 사용 금지, PyWinRT 사용)
winrt-runtime
winrt-Windows.Media.Control
winrt-Windows.Storage.Streams
requests
pystray
Pillow

## 파일 구조
apple_music_bridge/
├── main.py          # 진입점, 트레이 아이콘, asyncio 스레드 관리
├── smtc_reader.py   # SMTC 폴링, Apple Music 세션 탐색
├── lyrs_poster.py   # tuna-obs 포맷 변환 및 HTTP POST
└── requirements.txt