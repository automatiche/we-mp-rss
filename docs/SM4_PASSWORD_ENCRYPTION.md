# 口令 SM4 加密传输

等保扫描要求登录口令加密传输（"采用国家密码管理部门认可的加密方式"），实现为 SM4-CBC + 一次性密钥，改动最小化。

## 流程

1. 前端登录时先 `GET /api/v1/auth/salt` -> `{kid, key, iv}`（5 分钟有效，一次性）
2. 前端用 `sm-crypto` SM4-CBC 加密口令 -> hex 密文
3. `POST /api/v1/auth/login` 表单追加 `kid` 字段，`password` 为密文
4. 后端 `core/sm4crypt.py` 按 kid 解密，取出即焚；无 kid 的明文请求仍兼容

## 改动点

- `core/sm4crypt.py`：密钥下发/解密/即焚（TTLCache）
- `apis/auth.py`：`/salt` 接口 + `/login` 支持 kid 密文
- `web_ui/src/api/auth.ts`：`login()` 加密封装，salt 失败回退明文
- `requirements.txt`：gmssl、cachetools；`web_ui/package.json`：sm-crypto
- `static/`：前端构建产物已同步（本仓库惯例是提交编译后产物）

## 注意

- `/token` 接口（服务端调用，如 news-daily 的 wemp.py）未改，仍为明文表单——它是容器内网调用，不在漏洞范围
- 前端改完必须 `npm run build` 并同步产物到 `static/`，否则 Docker 镜像不生效
