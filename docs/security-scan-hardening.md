# 生产漏扫加固说明

适用部署：`news-daily/we-mp-rss:sm4` 派生镜像，编排入口为
`/home/yue/news/news-daily/docker-compose.yaml`。

## 端口与 RSS 访问边界

`/rss` 是 `news-backend` 的机器间订阅接口，而 8001 上的管理前端仍需供院内维护
人员访问。生产中的 `news-backend` 通过 Compose 网络访问
`http://we-mp-rss:8001`，因此可让机器间 RSS 请求保持直连，同时由 nginx 接管
宿主机 8001，仅限制来自院内网络的 RSS 请求。

先把 `news-daily/docker-compose.yaml` 中 `we-mp-rss` 的宿主机端口改为回环
`18001`，给 nginx 腾出 8001：

```yaml
services:
  we-mp-rss:
    ports:
      - "127.0.0.1:18001:8001"
```

不要同时保留原来的 `"8001:8001"`。然后在 nginx 中增加一个 8001 server：

```nginx
server {
    listen 8001 default_server;
    server_name _;

    # RSS/Atom 只供 Compose 网络内的 news-backend 使用。
    location = /rss  { return 403; }
    location ^~ /rss/ { return 403; }
    location = /feed  { return 403; }
    location ^~ /feed/ { return 403; }

    # 应用已默认关闭文档；nginx 再做一层明确拦截。
    location ~ ^/api/(docs|redoc|openapi\.json)$ { return 404; }

    location / {
        proxy_pass http://127.0.0.1:18001;
        proxy_http_version 1.1;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Port $server_port;
        proxy_buffering off;
        proxy_read_timeout 300s;
    }
}
```

这样：

- `news-backend -> http://we-mp-rss:8001` 的容器间访问保持不变；
- 院内维护人员仍可访问 `http://192.168.20.99:8001/login` 和管理前端；
- 院内未认证请求访问 `/rss`、`/rss/*`、`/feed/*` 会得到 403；
- SSRF、CORS 和点击劫持防护仍由应用层生效；
- 宿主机可通过 `http://127.0.0.1:18001` 直接检查容器后端。

修改后执行：

```bash
cd /home/yue/news/news-daily
docker compose config --quiet
docker compose up -d --no-deps --force-recreate we-mp-rss
sudo nginx -t
sudo systemctl reload nginx
docker compose ps we-mp-rss
```

从院内其他机器验证 `/login` 仍为 200，而 `/rss` 为 403；从宿主机验证
`http://127.0.0.1:18001/rss` 仍可访问。不要只依赖 UFW 拦截 Docker 发布端口。

## 应用安全配置

应用默认采用以下生产安全值：

```dotenv
API_DOCS_ENABLED=False
CORS_ALLOWED_ORIGINS=
```

同源部署不需要 CORS。确有独立前端跨域调用时，填写完整、精确的 Origin，多个值
用逗号分隔，例如：

```dotenv
CORS_ALLOWED_ORIGINS=https://news.example.internal,https://admin.example.internal
```

不要填写 `*`，也不要填写路径。修改 `.env` 或 `config.production.yaml` 后需要重建
`we-mp-rss` 容器，使启动期配置生效。

本次应用代码发布仍沿用既有派生镜像流程：代码合入并推送 `we-mp-rss/main`
后，在生产机执行：

```bash
cd /home/yue/news/news-daily
./update-we-mp-rss.sh
```

随后再应用前述 `127.0.0.1:18001:8001` 和 nginx 8001 配置。

## HTTPS 的影响

HTTPS 仅保护传输链路。本次未授权访问、SSRF、API 文档暴露、CORS 和点击劫持项
均不会因为启用 HTTPS 自动消失，仍需保留上述端口收口和应用加固。
