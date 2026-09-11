# iFLYTEK ASR Python 拡張

この拡張は WebSocket 経由で iFLYTEK リアルタイム文字起こしサービスに接続し、TEN Framework 標準の `ASRResult` を出力します。

## 機能

- PCM 音声を Base64 でエンコードし、開始・継続・終了フレームとして送信
- 中間結果、最終結果、単語タイミング、話者情報、ホットワード、声紋に対応
- iFLYTEK のエラーコードを含む TEN ASR エラーを出力
- 予期しない切断時に回数制限付き指数バックオフで再接続
- 分類・秘匿化ログ、10 MB の保持バッファ、接続遅延メトリクス、任意の PCM Dump を提供
- finalize のタイムアウト保護と完全な接続状態イベントを提供

## 設定

バージョン 0.2.0 以降、ベンダーおよび接続設定は必ず `params` オブジェクトに格納します。0.1.0 のトップレベル項目は受け付けません。`dump` と `dump_path` はトップレベルのままです。

接続には `url` と `biz_id` が必要です。既定では `IFLYTEK_ASR_URL` と `IFLYTEK_BIZ_ID` 環境変数を使用できます。入力は設定した `sample_rate` のモノラル 16-bit PCM としてください。複数言語は `zh|en` のように `|` で区切ります。

運用向け設定は `finalize_timeout`、`reconnect_delay`、`reconnect_max_delay`、`reconnect_max_attempts`、`buffer_max_bytes`（既定 10 MB）です。`dump=true` の場合、`dump_path` で PCM のディレクトリまたはファイルを指定できます。初回接続と途中の再接続の失敗は NON_FATAL として有限回再試行し、再試行回数を超過すると FATAL として報告されます。

完全な設定例は `README.zh-CN.md` を参照してください。
