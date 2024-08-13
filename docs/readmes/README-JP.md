<div align="center">

[![Follow on X](https://img.shields.io/twitter/follow/ten_platform?logo=X&color=%20%23f5f5f5)](https://twitter.com/intent/follow?screen_name=ten_platform)
[![Discussion posts](https://img.shields.io/github/discussions/rte-design/astra.ai?labelColor=%20%23FDB062&color=%20%23f79009)](https://github.com/rte-design/astra.ai/discussions/)
[![Commits](https://img.shields.io/github/commit-activity/m/rte-design/astra.ai?labelColor=%20%237d89b0&color=%20%235d6b98)](https://github.com/rte-design/astra.ai/graphs/commit-activity)
[![Issues closed](https://img.shields.io/github/issues-search?query=repo%3Arte-design%2Fastra.ai%20is%3Aclosed&label=issues%20closed&labelColor=green&color=green)](https://github.com/rte-design/ASTRA.ai/issues)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](https://github.com/rte-design/ASTRA.ai/pulls)
[![GitHub license](https://img.shields.io/badge/License-Apache_2.0-blue.svg?labelColor=%20%239b8afb&color=%20%237a5af8)](https://github.com/rte-design/ASTRA.ai/blob/main/LICENSE)
[![WeChat](https://img.shields.io/badge/WeChat-WeChat_Group-%2307C160?logo=wechat)](https://github.com/rte-design/ASTRA.ai/discussions/170)

[![Discord](https://dcbadge.vercel.app/api/server/VnPftUzAMJ)](https://discord.gg/VnPftUzAMJ)

[![GitHub watchers](https://img.shields.io/github/watchers/rte-design/astra.ai?style=social&label=Watch)](https://GitHub.com/rte-design/astra.ai/watchers/?WT.mc_id=academic-105485-koreyst)
[![GitHub forks](https://img.shields.io/github/forks/rte-design/astra.ai?style=social&label=Fork)](https://GitHub.com/rte-design/astra.ai/network/?WT.mc_id=academic-105485-koreyst)
[![GitHub stars](https://img.shields.io/github/stars/rte-design/astra.ai?style=social&label=Star)](https://GitHub.com/rte-design/astra.ai/stargazers/?WT.mc_id=academic-105485-koreyst)

<a href="../../README.md"><img alt="README in English" src="https://img.shields.io/badge/English-lightgrey"></a>
<a href="../readmes/README-CN.md"><img alt="简体中文" src="https://img.shields.io/badge/简体中文-lightgrey"></a>
<a href="../readmes/README-JP.md"><img alt="日本語" src="https://img.shields.io/badge/日本語-lightgrey"></a>
</div>

<div align="center">

[ドキュメント](https://astra-9.gitbook.io/ten-platform)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[クイックスタート](https://astra-9.gitbook.io/ten-platform/getting-started/quickstart)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[チュートリアル](https://app.gitbook.com/o/we7IoLK5sA6RQzhItfkW/s/4KgjqM5ChU0dSGjTLZmG/~/changes/6/tutorials/how-to-build-extension-with-go)


</div>

<br>

## Astra 音声エージェント

[Astra voice agent](https://theastra.ai) は、TEN を使用して構築された音声エージェントであり、マルチモーダルで低遅延の能力を示しています。

[![Showcase Astra voice agent](https://github.com/rte-design/docs/blob/main/assets/gifs/astra-voice-agent.gif?raw=true)](https://theastra.ai)

<br>
<h2>グラフデザイナーを使用して音声エージェントを構成する方法</h2>

### 前提条件
#### キー
- Agora App ID と App Certificate（[詳細はこちら](https://docs.agora.io/en/video-calling/get-started/manage-agora-account?platform=web)）
- Azure の [STT](https://azure.microsoft.com/en-us/products/ai-services/speech-to-text) と [TTS](https://azure.microsoft.com/en-us/products/ai-services/text-to-speech) API キー
- [OpenAI](https://openai.com/index/openai-api/) API キー
#### インストール
- [Docker](https://www.docker.com/) と [Docker Compose](https://docs.docker.com/compose/install/)
- [Node.js(LTS) v18](https://nodejs.org/en)
#### システム要件
- CPU >= 2 コア
- RAM >= 4 GB

#### Apple Silicon 上の Docker 設定
Apple Silicon Mac を使用している場合は、Docker の "Use Rosetta for x86_64/amd64 emulation on Apple Silicon" オプションのチェックを外す必要があります。そうしないと、サーバーが正常に動作しません。

<div align="center">

![Docker Setting](https://github.com/rte-design/docs/blob/main/assets/gifs/docker-setting.gif?raw=true)

</div>

### 次のステップ
#### 1. 設定ファイルの準備
プロジェクトをクローンした後、ルートディレクトリで以下のコマンドを実行して `property.json` と `.env` を作成します：
```bash
# .env ファイルの作成
cp ./.env.example ./.env

# property.json ファイルの作成
cp ./agents/property.json.example ./agents/property.json
```

#### 2. キーのバインド
`.env` ファイルを開き、対応するキーをバインドします。ここで異なるキーを設定することで、異なるエージェントを選択できます：
```
# Agora App ID と Agora App Certificate
AGORA_APP_ID=
AGORA_APP_CERTIFICATE=

# Extension: agora_rtc
# Azure STT キーとリージョン
AZURE_STT_KEY=
AZURE_STT_REGION=

# Extension: azure_tts
# Azure TTS キーとリージョン
AZURE_TTS_KEY=
AZURE_TTS_REGION=

# Extension: openai_chatgpt
# OpenAI API キー
OPENAI_API_KEY=
```

#### 3. Docker コンテナの起動
同じディレクトリで、Docker イメージを使用して Docker コンテナを構築します：
```bash
# Docker コンテナの起動：
docker compose up
```

#### 4. エージェントのビルドとサーバーの起動
別のターミナルウィンドウを開き、以下のコマンドを実行して Docker コンテナに入り、エージェントをビルドしてサーバーを起動します：
```bash
# コンテナに入り、エージェントをビルド
docker exec -it astra_agents_dev bash
make build

# ポート 8080 でサーバーを起動
make run-server
```

### 完了 🎉

ここまででローカルでの構築が完了しました。簡単な 4 ステップで、エージェントの体験が最大化されます！

#### Astra 音声エージェントの検証

ブラウザで `localhost:3000` を開いて音声エージェントを体験できます。

#### グラフデザイナーの検証

別のタブを開いて `localhost:3001` にアクセスし、TEN グラフデザイナー (ベータ版) を体験できます。簡単なドラッグアンドドロップと動的なノード接続で、Astra 音声エージェントを簡単にカスタマイズできます。

![TEN Graph Designer](https://github.com/rte-design/docs/blob/main/assets/gifs/graph-designer.gif?raw=true)

<br>
<h2>スターを付ける</h2>

頻繁に更新されるため、最新情報を見逃さないように、リポジトリにスターを付けてください。

![TEN star us gif](https://github.com/rte-design/docs/blob/main/assets/gifs/star-the-repo-confetti-higher-quality.gif?raw=true)

<br>
<h2>コミュニティに参加する</h2>

- [Discord](https://discord.gg/VnPftUzAMJ)：アプリケーションを共有し、コミュニティと交流するのに最適です。
- [WeChat Group](https://github.com/rte-design/ASTRA.ai/discussions/170): WeChat グループのコミュニティが好きな方は、ぜひご参加ください。
- [Github Discussion](https://github.com/rte-design/astra.ai/discussions)：フィードバックを提供し、質問するのに最適です。
- [GitHub Issues](https://github.com/rte-design/astra.ai/issues)：バグを報告し、新機能を提案するのに最適です。詳細については、[貢献ガイドライン](./docs/code-of-conduct/contributing.md)をご覧ください。
- [X（以前のTwitter）](https://twitter.com/intent/follow?screen_name=ten_platform)：エージェントを共有し、コミュニティと交流するのに最適です。

<br>
 <h2>コード貢献者</h2>

[![ASTRA](https://contrib.rocks/image?repo=rte-design/astra.ai)](https://github.com/rte-design/astra.ai/graphs/contributors)

<br>
<h2>貢献を歓迎します</h2>

貢献を歓迎します！まずは [貢献ガイドライン](../code-of-conduct/contributing.md) をお読みください。

<br>
<h2>ライセンス</h2>

このプロジェクトは Apache 2.0 ライセンスの下でライセンスされています。詳細については [LICENSE](LICENSE) をご覧ください。
