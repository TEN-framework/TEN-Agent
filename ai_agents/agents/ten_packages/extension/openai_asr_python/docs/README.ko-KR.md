# OpenAI ASR Python 확장

OpenAI의 자동 음성 인식(ASR) 서비스를 위한 Python 확장으로, OpenAI Realtime 전사 API(GA)를 사용하여 실시간 음성-텍스트 변환 기능을 제공하며 완전한 비동기 작업을 지원합니다.

## 기능

- **완전한 비동기 지원**: 고성능 음성 인식을 위한 완전한 비동기 아키텍처로 구축
- **실시간 스트리밍**: OpenAI의 WebSocket API를 사용한 낮은 지연 시간의 실시간 오디오 스트리밍
- **OpenAI Realtime API**: GA `session.update`를 통해 OpenAI Realtime 전사 API 사용
- **PCM16 오디오**: 임의의 입력 샘플링 레이트를 수용하며 전송 전 24 kHz PCM16으로 리샘플링
- **오디오 덤프**: 디버깅 및 분석을 위한 선택적 오디오 녹음
- **구성 가능한 로깅**: 디버깅을 위한 조정 가능한 로그 레벨
- **오류 처리**: 상세한 로깅을 통한 포괄적인 오류 처리
- **다국어 지원**: OpenAI의 전사 모델을 통해 여러 언어 지원
- **노이즈 감소**: 선택적 노이즈 감소 기능
- **턴 감지**: 대화 분석을 위한 구성 가능한 턴 감지

## 구성

확장에는 다음 구성 매개변수가 필요합니다:

### 필수 매개변수

- `api_key`: 인증을 위한 OpenAI API 키
- `params`: 오디오 형식 및 전사 설정을 포함한 OpenAI ASR 요청 매개변수

### 선택적 매개변수

- `organization`: OpenAI 조직 ID (선택사항)
- `project`: OpenAI 프로젝트 ID (선택사항)
- `base_url`: 사용자 정의 WebSocket 기본 URL (선택사항)
- `dump`: 오디오 덤프 활성화 (기본값: false)
- `dump_path`: 덤프된 오디오 파일의 경로 (기본값: "openai_asr_in.pcm")
- `log_level`: 로그 레벨 (기본값: "INFO")

### 구성 예시

```json
{
  "params": {
    "api_key": "your_openai_api_key",
    "input_audio_format": "pcm16",
    "input_audio_transcription": {
      "model": "whisper-1",
      "prompt": "",
      "language": "en"
    },
    "turn_detection": {
      "type": "server_vad",
      "threshold": 0.5,
      "prefix_padding_ms": 300,
      "silence_duration_ms": 500
    }
  },
  "dump": false,
  "log_level": "INFO"
}
```

`organization`, `project`, `base_url` 등 선택적 연결 매개변수는 `params` 아래에 둡니다.

## API

확장은 `AsyncASRBaseExtension` 인터페이스를 구현하고 다음 주요 메서드를 제공합니다:

### 핵심 메서드

- `on_init()`: OpenAI ASR 클라이언트 및 구성 초기화
- `start_connection()`: OpenAI ASR 서비스에 대한 연결 설정
- `stop_connection()`: ASR 서비스에 대한 연결 종료
- `send_audio()`: 인식을 위한 오디오 프레임 전송
- `finalize()`: 현재 인식 세션 완료

### 이벤트 핸들러

- `on_asr_start()`: ASR 세션이 시작될 때 호출
- `on_asr_delta()`: 전사 델타를 받았을 때 호출
- `on_asr_completed()`: 전사가 완료되었을 때 호출
- `on_asr_committed()`: 오디오 버퍼가 커밋되었을 때 호출
- `on_asr_server_error()`: 서버 오류가 발생했을 때 호출
- `on_asr_client_error()`: 클라이언트 오류가 발생했을 때 호출

## 의존성

- `typing_extensions`: 타입 힌트용
- `pydantic`: 구성 검증 및 데이터 모델용
- `websockets`: WebSocket 통신용
- `openai`: OpenAI Python 클라이언트 라이브러리
- `pytest`: 테스트용 (개발 의존성)

## 개발

### 빌드

확장은 TEN Framework 빌드 시스템의 일부로 빌드됩니다. 추가 빌드 단계가 필요하지 않습니다.

### 테스트

단위 테스트 실행:

```bash
pytest tests/
```

확장에는 다음 포괄적인 테스트가 포함되어 있습니다:
- 구성 검증
- 오디오 처리
- 오류 처리
- 연결 관리
- 전사 결과 처리

## 사용법

1. **설치**: 확장은 TEN Framework와 함께 자동으로 설치됩니다
2. **구성**: OpenAI API 자격 증명 및 매개변수 설정
3. **통합**: TEN Framework ASR 인터페이스를 통해 확장 사용
4. **모니터링**: 디버깅 및 모니터링을 위해 로그 확인

## 오류 처리

확장은 다음 방법으로 상세한 오류 정보를 제공합니다:
- 모듈 오류 코드
- OpenAI 특정 오류 세부사항
- 포괄적인 로깅
- 우아한 성능 저하

## 성능

- **낮은 지연 시간**: OpenAI의 스트리밍 API를 사용한 실시간 처리 최적화
- **높은 처리량**: 효율적인 오디오 프레임 처리
- **메모리 효율성**: 최소한의 메모리 사용량
- **연결 재사용**: 지속적인 WebSocket 연결 유지

## 보안

- **자격 증명 암호화**: 구성에서 민감한 자격 증명 암호화
- **안전한 통신**: OpenAI에 대한 안전한 WebSocket 연결 사용
- **입력 검증**: 포괄적인 입력 검증 및 살균

## 지원되는 OpenAI 모델

확장은 다양한 OpenAI 전사 모델을 지원합니다:
- `whisper-1`: 표준 Whisper 모델
- `gpt-4o-transcribe`: GPT-4o 전사 모델
- `gpt-4o-mini-transcribe`: GPT-4o mini 전사 모델

## 오디오 형식 지원

- **PCM16** (권장): 확장은 입력 오디오를 24 kHz PCM16으로 리샘플링한 뒤 OpenAI로 전송합니다. `input_audio_format`을 `"pcm16"`으로 설정하세요.
- **G711 U-law / A-law**: 향후 호환을 위해 구성에서 허용되지만, 확장은 현재 이 설정과 관계없이 항상 리샘플링된 PCM16을 전송합니다.

## 문제 해결

### 일반적인 문제

1. **연결 실패**: API 키 및 네트워크 연결 확인
2. **오디오 품질 문제**: 오디오 형식 및 샘플링 레이트 설정 확인
3. **성능 문제**: 버퍼 설정 및 모델 선택 조정
4. **로깅 문제**: 적절한 로그 레벨 구성

### 디버그 모드

구성에서 `dump: true`를 설정하여 디버그 모드를 활성화하고 분석을 위해 오디오를 녹음합니다.

## 라이선스

이 확장은 TEN Framework의 일부이며 Apache License, Version 2.0에 따라 라이선스됩니다.
