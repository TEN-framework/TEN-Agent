# OpenAI ASR Python 擴充

一個用於 OpenAI 自動語音識別 (ASR) 服務的 Python 擴充，提供即時語音轉文字轉換功能，完全支援非同步操作，使用 OpenAI Realtime 轉錄 API（GA 正式版）。

## 功能特性

- **完全非同步支援**: 採用完整的非同步架構，實現高效能語音識別
- **即時串流處理**: 使用 OpenAI 的 WebSocket API 支援低延遲即時音訊串流
- **OpenAI Realtime API**: 透過 GA 版 `session.update` 使用 OpenAI Realtime 轉錄 API
- **PCM16 音訊**: 接受任意輸入取樣率，傳送前重採樣為 24 kHz PCM16
- **音訊轉儲**: 可選的音訊錄製功能，用於除錯和分析
- **可設定日誌**: 可調整的日誌級別，便於除錯
- **錯誤處理**: 全面的錯誤處理和詳細日誌記錄
- **多語言支援**: 透過 OpenAI 的轉錄模型支援多種語言
- **降噪功能**: 可選的降噪功能
- **對話檢測**: 可設定的對話檢測功能，用於對話分析

## 設定

擴充需要以下設定參數：

### 必需參數

- `api_key`: OpenAI API 金鑰，用於身份驗證
- `params`: OpenAI ASR 請求參數，包括音訊格式和轉錄設定

### 可選參數

- `organization`: OpenAI 組織 ID（可選）
- `project`: OpenAI 專案 ID（可選）
- `base_url`: 自訂 WebSocket 基礎 URL（可選）
- `dump`: 啟用音訊轉儲（預設：false）
- `dump_path`: 轉儲音訊檔案的路徑（預設："openai_asr_in.pcm"）
- `log_level`: 日誌級別（預設："INFO"）

### 設定範例

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

`organization`、`project`、`base_url` 等可選連線參數應放在 `params` 下。

## API

擴充實現了 `AsyncASRBaseExtension` 介面，提供以下關鍵方法：

### 核心方法

- `on_init()`: 初始化 OpenAI ASR 客戶端和設定
- `start_connection()`: 建立與 OpenAI ASR 服務的連線
- `stop_connection()`: 關閉與 ASR 服務的連線
- `send_audio()`: 傳送音訊幀進行識別
- `finalize()`: 完成當前識別會話

### 事件處理器

- `on_asr_start()`: ASR 會話開始時呼叫
- `on_asr_delta()`: 收到轉錄增量時呼叫
- `on_asr_completed()`: 轉錄完成時呼叫
- `on_asr_committed()`: 音訊緩衝區提交時呼叫
- `on_asr_server_error()`: 伺服器錯誤時呼叫
- `on_asr_client_error()`: 客戶端錯誤時呼叫

## 依賴項

- `typing_extensions`: 用於型別提示
- `pydantic`: 用於設定驗證和資料模型
- `websockets`: 用於 WebSocket 通訊
- `openai`: OpenAI Python 客戶端程式庫
- `pytest`: 用於測試（開發依賴）

## 開發

### 建置

擴充作為 TEN Framework 建置系統的一部分進行建置。無需額外的建置步驟。

### 測試

執行單元測試：

```bash
pytest tests/
```

擴充包含全面的測試：
- 設定驗證
- 音訊處理
- 錯誤處理
- 連線管理
- 轉錄結果處理

## 使用方法

1. **安裝**: 擴充隨 TEN Framework 自動安裝
2. **設定**: 設定您的 OpenAI API 憑證和參數
3. **整合**: 透過 TEN Framework ASR 介面使用擴充
4. **監控**: 檢查日誌以進行除錯和監控

## 錯誤處理

擴充透過以下方式提供詳細的錯誤資訊：
- 模組錯誤程式碼
- OpenAI 特定錯誤詳情
- 全面的日誌記錄
- 優雅降級

## 效能

- **低延遲**: 使用 OpenAI 的串流 API 最佳化即時處理
- **高吞吐量**: 高效的音訊幀處理
- **記憶體高效**: 最小的記憶體佔用
- **連線複用**: 維護持久的 WebSocket 連線

## 安全性

- **憑證加密**: 敏感憑證在設定中加密
- **安全通訊**: 使用與 OpenAI 的安全 WebSocket 連線
- **輸入驗證**: 全面的輸入驗證和清理

## 支援的 OpenAI 模型

擴充支援各種 OpenAI 轉錄模型：
- `whisper-1`: 標準 Whisper 模型
- `gpt-4o-transcribe`: GPT-4o 轉錄模型
- `gpt-4o-mini-transcribe`: GPT-4o mini 轉錄模型

## 音訊格式支援

- **PCM16**（建議）：擴充會將輸入音訊重採樣為 24 kHz PCM16 後傳送給 OpenAI。請將 `input_audio_format` 設為 `"pcm16"`。
- **G711 U-law / A-law**：設定中可接受以便向前相容，但擴充目前無論此項如何設定，實際始終傳送重採樣後的 PCM16。

## 故障排除

### 常見問題

1. **連線失敗**: 檢查 API 金鑰和網路連線
2. **音訊品質問題**: 驗證音訊格式和取樣率設定
3. **效能問題**: 調整緩衝區設定和模型選擇
4. **日誌問題**: 設定適當的日誌級別

### 除錯模式

透過在設定中設定 `dump: true` 啟用除錯模式，以錄製音訊進行分析。

## 授權

此擴充是 TEN Framework 的一部分，根據 Apache License, Version 2.0 授權。
