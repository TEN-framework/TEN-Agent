## 哪里申请 Agora APP ID 和 Agora APP Certificate?

大中华地区的用户可以直接在 [声网](https://console.shengwang.cn/) 创建项目，然后 ID 和 Certificate 会自动生成。

## Windows 设置（必读）

在 Windows 系统中，Git 会自动在每行末尾添加回车符(\r)，这会导致运行服务器时出现 `agents/bin/start: not found` 错误。

**如果您遇到这个问题**，请按照以下步骤操作：
1. 完全删除当前项目文件夹
2. 运行以下命令来禁用 Git 的自动 CRLF：

```bash
git config --global core.autocrlf false
```

## 如何查看自己的网络连接情况？

请确保您的 **HTTPS** 和 **SSH** 都已连接到互联网。

测试 **HTTPS**:

```bash
ping www.google.com

# You should see the following output:
PING google.com (198.18.1.94): 56 data bytes
64 bytes from 198.18.1.94: icmp_seq=0 ttl=64 time=0.099 ms
64 bytes from 198.18.1.94: icmp_seq=1 ttl=64 time=0.121 ms
```

测试 **SSH**:

```
curl www.google.com

# You should see the following output:
<html>
<head><title>301 Moved Permanently</title></head>
<body>
<h1>301 Moved Permanently</h1>
</body>
</html>
```

