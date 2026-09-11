# OpenAI ASR Python 拡張

OpenAI の自動音声認識 (ASR) サービスのための Python 拡張で、OpenAI Realtime 転写 API（GA）を使用してリアルタイム音声テキスト変換機能を提供し、完全な非同期操作をサポートします。

## 機能

- **完全非同期サポート**: 高性能音声認識のための完全な非同期アーキテクチャで構築
- **リアルタイムストリーミング**: OpenAI の WebSocket API を使用した低遅延リアルタイム音声ストリーミング
- **OpenAI Realtime API**: GA 版 `session.update` 経由で OpenAI Realtime 転写 API を使用
- **PCM16 音声**: 任意の入力サンプリングレートを受け付け、送信前に 24 kHz PCM16 にリサンプリング
- **音声ダンプ**: デバッグと分析のためのオプション音声録音
- **設定可能なログ**: デバッグのための調整可能なログレベル
- **エラーハンドリング**: 詳細なログ記録による包括的なエラー処理
- **多言語サポート**: OpenAI の転写モデルを通じて複数の言語をサポート
- **ノイズリダクション**: オプションのノイズリダクション機能
- **ターン検出**: 会話分析のための設定可能なターン検出

## 設定

拡張には以下の設定パラメータが必要です：

### 必須パラメータ

- `api_key`: 認証のための OpenAI API キー
- `params`: 音声形式と転写設定を含む OpenAI ASR リクエストパラメータ

### オプションパラメータ

- `organization`: OpenAI 組織 ID（オプション）
- `project`: OpenAI プロジェクト ID（オプション）
- `base_url`: カスタム WebSocket ベース URL（オプション）
- `dump`: 音声ダンプを有効化（デフォルト：false）
- `dump_path`: ダンプ音声ファイルのパス（デフォルト："openai_asr_in.pcm"）
- `log_level`: ログレベル（デフォルト："INFO"）

### 設定例

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

`organization`、`project`、`base_url` などのオプション接続パラメータは `params` 配下に配置します。

## API

拡張は `AsyncASRBaseExtension` インターフェースを実装し、以下の主要メソッドを提供します：

### コアメソッド

- `on_init()`: OpenAI ASR クライアントと設定を初期化
- `start_connection()`: OpenAI ASR サービスへの接続を確立
- `stop_connection()`: ASR サービスへの接続を閉じる
- `send_audio()`: 認識のための音声フレームを送信
- `finalize()`: 現在の認識セッションを完了

### イベントハンドラー

- `on_asr_start()`: ASR セッション開始時に呼び出される
- `on_asr_delta()`: 転写デルタを受信した時に呼び出される
- `on_asr_completed()`: 転写完了時に呼び出される
- `on_asr_committed()`: 音声バッファがコミットされた時に呼び出される
- `on_asr_server_error()`: サーバーエラー発生時に呼び出される
- `on_asr_client_error()`: クライアントエラー発生時に呼び出される

## 依存関係

- `typing_extensions`: 型ヒント用
- `pydantic`: 設定検証とデータモデル用
- `websockets`: WebSocket 通信用
- `openai`: OpenAI Python クライアントライブラリ
- `pytest`: テスト用（開発依存関係）

## 開発

### ビルド

拡張は TEN Framework ビルドシステムの一部としてビルドされます。追加のビルド手順は不要です。

### テスト

ユニットテストを実行：

```bash
pytest tests/
```

拡張には以下の包括的なテストが含まれています：
- 設定検証
- 音声処理
- エラー処理
- 接続管理
- 転写結果処理

## 使用方法

1. **インストール**: 拡張は TEN Framework と共に自動的にインストールされます
2. **設定**: OpenAI API 認証情報とパラメータを設定
3. **統合**: TEN Framework ASR インターフェースを通じて拡張を使用
4. **監視**: デバッグと監視のためにログを確認

## エラー処理

拡張は以下の方法で詳細なエラー情報を提供します：
- モジュールエラーコード
- OpenAI 固有のエラー詳細
- 包括的なログ記録
- グレースフルデグラデーション

## パフォーマンス

- **低遅延**: OpenAI のストリーミング API を使用したリアルタイム処理の最適化
- **高スループット**: 効率的な音声フレーム処理
- **メモリ効率**: 最小限のメモリ使用量
- **接続再利用**: 永続的な WebSocket 接続の維持

## セキュリティ

- **認証情報暗号化**: 設定内の機密認証情報の暗号化
- **安全な通信**: OpenAI への安全な WebSocket 接続の使用
- **入力検証**: 包括的な入力検証とサニタイゼーション

## サポートされる OpenAI モデル

拡張は様々な OpenAI 転写モデルをサポートします：
- `whisper-1`: 標準 Whisper モデル
- `gpt-4o-transcribe`: GPT-4o 転写モデル
- `gpt-4o-mini-transcribe`: GPT-4o mini 転写モデル

## 音声形式サポート

- **PCM16**（推奨）: 拡張は入力音声を 24 kHz PCM16 にリサンプリングしてから OpenAI に送信します。`input_audio_format` は `"pcm16"` に設定してください。
- **G711 U-law / A-law**: 将来互換のため設定では受け付けますが、拡張は現在この設定に関わらず常にリサンプリング済み PCM16 を送信します。

## トラブルシューティング

### 一般的な問題

1. **接続失敗**: API キーとネットワーク接続を確認
2. **音声品質の問題**: 音声形式とサンプリングレート設定を確認
3. **パフォーマンスの問題**: バッファ設定とモデル選択を調整
4. **ログの問題**: 適切なログレベルを設定

### デバッグモード

設定で `dump: true` を設定してデバッグモードを有効化し、分析のために音声を録音します。

## ライセンス

この拡張は TEN Framework の一部で、Apache License, Version 2.0 の下でライセンスされています。
