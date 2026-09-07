# 訊飛 ASR Python 擴充

此擴充透過 WebSocket 接入訊飛即時轉寫服務，並輸出 TEN Framework 標準 `ASRResult`。

## 功能

- 依訊飛協議傳送首幀、中間幀與尾幀，PCM 音訊使用 Base64 編碼
- 支援中間與最終結果、詞邊界、說話人資訊、熱詞和聲紋庫
- 輸出包含訊飛錯誤碼的 TEN ASR 錯誤訊息
- 意外斷線後以有限次數的指數退避策略重連
- 提供分類及脫敏日誌、10 MB 保留緩衝、連線延遲指標與可選 PCM Dump
- 提供 finalize 超時保護及完整連線狀態事件

## 設定

自 0.2.0 起，供應商與連線設定必須統一放在 `params` 物件中，不再接受 0.1.0
的頂層欄位。`dump` 與 `dump_path` 維持為擴充頂層屬性。

服務串接必須提供 `url` 與 `biz_id`，預設可由 `IFLYTEK_ASR_URL`、`IFLYTEK_BIZ_ID` 環境變數注入。輸入音訊必須是符合 `sample_rate` 的單聲道 16 位元 PCM。多語種以 `|` 分隔，例如 `zh|en`。

生產控制包括 `finalize_timeout`、`reconnect_delay`、`reconnect_max_delay`、`reconnect_max_attempts` 與 `buffer_max_bytes`（預設 10 MB）。設定 `dump=true` 後可用 `dump_path` 指定 PCM 目錄或檔案。初次連線及中間重試失敗會上報 NON_FATAL 並繼續有限次重試；重試耗盡後上報 FATAL。

完整設定範例請參考 `README.zh-CN.md`。
