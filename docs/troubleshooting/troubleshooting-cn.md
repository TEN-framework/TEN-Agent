## 哪里申请 Agora APP ID 和 Agora APP Certificate?

大中华地区的用户可以直接在 [声网](https://console.shengwang.cn/) 创建项目，然后 ID 和 Certificate 会自动生成。

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

## 遇到 /app/agents/bin/start: not found 错误怎么办？

1. 有可能是权限的问题，所以可以 `cd /app/agents/bin/start` 过去，看下文件是否存在。
如果存在，可以尝试 `chmod +x start` 赋予权限。

1. 如果 `cd /app/agents/bin/start` 文件不存在， 有可能是因为 Windows line-ending 的问题，可以尝试 `git config --global core.autocrlf true` 来解决。 然后再重新 clone 代码。