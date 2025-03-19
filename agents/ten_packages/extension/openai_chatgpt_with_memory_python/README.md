# OpenAI ChatGPT With Memory Python Extension

基于OpenAI API的具有长期记忆功能的聊天机器人扩展。

## 功能

1. 支持基于语义的长期记忆存储和检索
2. 使用Qdrant向量数据库存储对话历史
3. 在回答问题时自动检索和利用相关的历史对话
4. 支持清除记忆的命令
5. 支持所有OpenAI ChatGPT的功能

## 配置

在`property.json`中配置以下参数：

- `api_key`: OpenAI API密钥
- `model`: 使用的模型，默认为"gpt-4o"
- `max_tokens`: 生成的最大token数，默认为512
- `prompt`: 系统提示词
- `greeting`: 初始问候语
- `qdrant_host`: Qdrant服务器地址，默认为"qdrant"
- `qdrant_port`: Qdrant服务器端口，默认为6333

## 依赖

- openai
- numpy
- requests[socks]
- pillow
- qdrant_client
- sentence-transformers

## 使用

1. 确保Qdrant向量数据库已运行
2. 将扩展添加到您的TEN Agent项目中
3. 配置必要的环境变量和属性
4. 使用与标准ChatGPT扩展相同的方式进行交互

### 记忆管理命令

清除所有记忆：

```json
{
  "name": "clear_memory"
}
```

## 示例

用户: "你好，我叫张三"
助手: "你好张三，很高兴认识你！有什么我可以帮助你的吗？"

用户: "我的爱好是什么？"
助手: "从我们之前的对话中，我没有获取到关于你爱好的信息。你叫张三，但你还没有告诉我你的爱好是什么。你想分享一下吗？"

用户: "我喜欢打篮球和弹钢琴"
助手: "了解了，张三。你喜欢打篮球和弹钢琴，这两个爱好都很棒！篮球是一项很好的体育运动，能锻炼身体协调性和团队合作精神，而钢琴则能培养艺术感和专注力。你弹钢琴有多久了？打篮球是业余爱好还是参加过什么比赛呢？"

用户: "我的爱好是什么？"
助手: "根据我们之前的对话，你告诉我你喜欢打篮球和弹钢琴。这两项活动都是你的爱好。" 