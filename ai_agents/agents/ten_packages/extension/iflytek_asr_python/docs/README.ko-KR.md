# iFLYTEK ASR Python 확장

이 확장은 WebSocket으로 iFLYTEK 실시간 전사 서비스에 연결하고 TEN Framework 표준 `ASRResult`를 출력합니다.

## 기능

- PCM 오디오를 Base64로 인코딩하여 시작, 중간, 종료 프레임으로 전송
- 중간 및 최종 결과, 단어 시간, 화자 정보, 핫워드, 성문 데이터 지원
- iFLYTEK 오류 코드를 포함한 TEN ASR 오류 출력
- 예기치 않은 연결 종료 시 제한된 지수 백오프로 재연결
- 분류 및 비식별화 로그, 10 MB 유지 버퍼, 연결 지연 메트릭, 선택적 PCM Dump 제공
- finalize 시간 초과 보호 및 전체 연결 상태 이벤트 제공

## 설정

버전 0.2.0부터 공급자 및 연결 설정은 반드시 `params` 객체 안에 둡니다. 0.1.0의 최상위 필드는 허용하지 않습니다. `dump`와 `dump_path`는 최상위 속성으로 유지됩니다.

서비스 연결에는 `url`과 `biz_id`가 필요합니다. 기본 속성은 `IFLYTEK_ASR_URL` 및 `IFLYTEK_BIZ_ID` 환경 변수를 사용할 수 있습니다. 입력은 설정된 `sample_rate`의 모노 16비트 PCM이어야 합니다. 여러 언어는 `zh|en`처럼 `|`로 구분합니다.

운영 설정에는 `finalize_timeout`, `reconnect_delay`, `reconnect_max_delay`, `reconnect_max_attempts`, `buffer_max_bytes`(기본 10 MB)가 있습니다. `dump=true`로 설정하면 `dump_path`에서 PCM 디렉터리 또는 파일을 지정할 수 있습니다. 최초 연결 및 중간 재연결 실패는 NON_FATAL로 보고하고 제한된 재시도를 계속하며, 재시도를 모두 소진하면 FATAL로 보고합니다.

전체 설정 예제는 `README.zh-CN.md`를 참고하십시오.
