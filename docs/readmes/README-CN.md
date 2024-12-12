![Banner de TEN Agent](https://github.com/TEN-framework/docs/blob/main/assets/jpg/banner.jpg?raw=true)

<div align="center">

[![Follow on X](https://img.shields.io/twitter/follow/TenFramework?logo=X&color=%20%23f5f5f5)](https://twitter.com/intent/follow?screen_name=TenFramework)
[![Discussion posts](https://img.shields.io/github/discussions/TEN-framework/ten-agent?labelColor=%20%23FDB062&color=%20%23f79009)](https://github.com/TEN-framework/ten-agent/discussions/)
[![Commits](https://img.shields.io/github/commit-activity/m/TEN-framework/ten-agent?labelColor=%20%237d89b0&color=%20%235d6b98)](https://github.com/TEN-framework/ten-agent/graphs/commit-activity)
[![Issues closed](https://img.shields.io/github/issues-search?query=repo%3ATEN-framework%2Ften-agent%20is%3Aclosed&label=issues%20closed&labelColor=green&color=green)](https://github.com/TEN-framework/ten-agent/issues)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square)](https://github.com/TEN-framework/ten-agent/pulls)
[![GitHub license](https://img.shields.io/badge/License-Apache_2.0-blue.svg?labelColor=%20%239b8afb&color=%20%237a5af8)](https://github.com/TEN-framework/ten-agent/blob/main/LICENSE)
[![WeChat](https://img.shields.io/badge/WeChat-WeChat_Group-%2307C160?logo=wechat)](https://github.com/TEN-framework/ten-agent/discussions/170)

[![Discord](https://dcbadge.vercel.app/api/server/VnPftUzAMJ)](https://discord.gg/VnPftUzAMJ)

<a href="https://trendshift.io/repositories/11978" target="_blank"><img src="https://trendshift.io/api/badge/repositories/11978" alt="TEN-framework%2FTEN-Agent | Trendshift" style="width: 250px; height: 55px;" width="250" height="55"/></a>

[![GitHub watchers](https://img.shields.io/github/watchers/TEN-framework/ten-agent?style=social&label=Watch)](https://GitHub.com/TEN-framework/ten-agent/watchers/?WT.mc_id=academic-105485-koreyst)
[![GitHub forks](https://img.shields.io/github/forks/TEN-framework/ten-agent?style=social&label=Fork)](https://GitHub.com/TEN-framework/ten-agent/network/?WT.mc_id=academic-105485-koreyst)
[![GitHub stars](https://img.shields.io/github/stars/TEN-framework/ten-agent?style=social&label=Star)](https://GitHub.com/TEN-framework/ten-agent/stargazers/?WT.mc_id=academic-105485-koreyst)

<a href="https://github.com/TEN-framework/ten-agent/blob/main/README.md"><img alt="README in English" src="https://img.shields.io/badge/English-lightgrey"></a>
<a href="https://github.com/TEN-framework/ten-agent/blob/main/docs/readmes/README-CN.md"><img alt="简体中文操作指南" src="https://img.shields.io/badge/简体中文-lightgrey"></a>
<a href="https://github.com/TEN-framework/ten-agent/blob/main/docs/readmes/README-JP.md"><img alt="日本語のREADME" src="https://img.shields.io/badge/日本語-lightgrey"></a>
<a href="https://github.com/TEN-framework/ten-agent/blob/main/docs/readmes/README-KR.md"><img alt="README in 한국어" src="https://img.shields.io/badge/한국어-lightgrey"></a>
<a href="https://github.com/TEN-framework/ten-agent/blob/main/docs/readmes/README-ES.md"><img alt="README en Español" src="https://img.shields.io/badge/Español-lightgrey"></a>
<a href="https://github.com/TEN-framework/ten-agent/blob/main/docs/readmes/README-FR.md"><img alt="README en Français" src="https://img.shields.io/badge/Français-lightgrey"></a>
<a href="https://github.com/TEN-framework/ten-agent/blob/main/docs/readmes/README-IT.md"><img alt="README in Italiano" src="https://img.shields.io/badge/Italiano-lightgrey"></a>

</div>

<div align="center">

[文档](https://doc.theten.ai)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[快速开始](https://doc.theten.ai/getting-started/quickstart)
<span>&nbsp;&nbsp;•&nbsp;&nbsp;</span>
[TEN Framework 仓库](https://github.com/TEN-framework/ten_framework)


</div>

<br>
<h2>本地跑起 TEN Agent Playground

### 先决条件

| 类别 | 要求 |
|----------|-------------|
| **Keys** | • [ App ID ](https://console.shengwang.cn) 和 [ App Certificate ](https://console.shengwang.cn)（[注册教程](https://doc.shengwang.cn/doc/console/general/quickstart#%E6%B3%A8%E5%86%8C%E8%B4%A6%E5%8F%B7)） <br>• [OpenAI](https://openai.com/index/openai-api/) API 密钥<br>• [ Deepgram ](https://deepgram.com/) ASR（注册即可获得免费额度）<br>• [ FishAudio ](https://fish.audio/) TTS（注册即可获得免费额度）|
| **安装要求** | • [Docker](https://www.docker.com/) / [Docker Compose](https://docs.docker.com/compose/)<br>• [Node.js(LTS) v18](https://nodejs.org/en) |
| **最低系统要求** | • CPU >= 2核<br>• 内存 >= 4 GB |

<br>

#### macOS：Apple Silicon 上的 Docker 设置

对于 Apple Silicon Mac，请在 Docker 设置中取消勾选"使用 Rosetta 进行 x86/amd64 模拟"选项。注意：这可能会导致在 ARM 上的构建时间变慢，但部署到 x64 服务器时性能将恢复正常。

![Docker 设置](https://github.com/TEN-framework/docs/blob/main/assets/gif/docker_setting.gif?raw=true)

<br>

#### 设置国内代理

如果在国内，我们强烈建议在 SSH 中把代理打开，下载和安装的依赖的时候会更加丝滑。如果遇到更多问题，请参考 [问题排查](../troubleshooting/troubleshooting-cn.md)。

```bash
# 如果用的代理软件没有增强模式的话， 建议手动把所有代理协议都打开
# export 的有效期为一个 session
export https_proxy=http://127.0.0.1:（端口例如 7890） 
export http_proxy=http://127.0.0.1:（端口例如 7890） 
export all_proxy=socks5://127.0.0.1:（端口例如 7890）

# Docker
export https_proxy=http://host.docker.internal:（端口例如 7890）
export http_proxy=http://host.docker.internal:（端口例如 7890）
export all_proxy=http://host.docker.internal:（端口例如 7890）

# GO 代理设置
export GOPROXY=https://goproxy.cn,direct

# pip 代理设置, 此设置需要先安装 pip
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

<br>

#### 下一步

#### 1. 创建 `.env` 文件

```bash
cp ./.env.example ./.env
```

#### 2. 在 `.env` 中设置 Agora App ID 和 App Certificate

```bash
AGORA_APP_ID=
AGORA_APP_CERTIFICATE=
```

#### 3. 启动代理开发容器
```bash
docker compose up -d
```

#### 4. 进入容器
```bash
docker exec -it ten_agent_dev bash
```

#### 5. 构建代理
```bash
task use
```

#### 6. 启动网络服务器
```bash
task run
```

#### 7. 编辑 playground 设置
在 [localhost:3000](http://localhost:3000) 打开 playground 来配置你的代理。
 1. 选择图表类型（例如：语音代理、实时代理）
 2. 选择对应的模块
 3. 选择扩展并配置其 API 密钥设置

![模块示例](https://github.com/TEN-framework/docs/blob/main/assets/gif/module-example.gif?raw=true)

<br>
<h2>点星收藏</h2>

我们更新频繁，不想错过的话，请给我们的 repo 点星，以便获得第一时间的更新.

![TEN star us gif](https://github.com/TEN-framework/docs/blob/main/assets/gif/star_us_2.gif?raw=true)

<br>
<h2>加入社区</h2>

- [Discord](https://discord.gg/VnPftUzAMJ)：非常适合分享您的应用程序并与社区互动。
- [WeChat Group](https://github.com/TEN-framework/ten-agent/discussions/170): 如果喜欢用微信群的社区，欢迎加入。
- [Github Discussion](https://github.com/TEN-framework/ten-agent/discussions)：非常适合提供反馈和提问。
- [GitHub Issues](https://github.com/TEN-framework/ten-agent/issues)：最适合报告错误和提出新功能。有关更多详细信息，请参阅我们的[贡献指南](./docs/code-of-conduct/contributing.md)。
- [X/Twitter](https://img.shields.io/twitter/follow/TenFramework?logo=X&color=%20%23f5f5f5)：非常适合分享您的代理并与社区互动。

<br>
 <h2>代码贡献者</h2>

[![TEN Agent](https://contrib.rocks/image?repo=TEN-framework/ten-agent)](https://github.com/TEN-framework/ten-agent/graphs/contributors)

<br>
<h2>欢迎贡献</h2>

欢迎贡献！请先阅读 [贡献指南](../code-of-conduct/contributing.md)。

<br>
<h2>许可证授权</h2>

本项目使用 Apache 2.0 许可证授权 - 详细信息请参阅 [LICENSE](../../LICENSE)。
