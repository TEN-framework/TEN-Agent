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