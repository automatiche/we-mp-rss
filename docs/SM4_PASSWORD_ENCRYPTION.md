# 口令 SM4 加密传输

等保扫描要求登录口令加密传输（"采用国家密码管理部门认可的加密方式"），实现为 SM4-CBC + 一次性密钥，改动最小化。

## 流程

1. 前端登录时先 `GET /api/v1/wx/auth/salt` -> `{kid, key, iv}`（5 分钟有效，一次性）
2. 前端用 `sm-crypto` SM4-CBC 加密口令 -> hex 密文
3. `POST /api/v1/wx/auth/login` 表单追加 `kid` 字段，`password` 为密文
4. 后端 `core/sm4crypt.py` 按 kid 解密，取出即焚；无 kid 的旧脚本请求仍兼容

## 改动点

- `core/sm4crypt.py`：密钥下发/解密/即焚（TTLCache）
- `apis/auth.py`：`/salt` 接口 + `/login` 支持 kid 密文
- `web_ui/src/api/auth.ts`：`login()` 加密封装
- `requirements.txt`：gmssl、cachetools；`web_ui/package.json`：sm-crypto
- `Dockerfiles/Dockerfile.security`：构建镜像时编译前端并覆盖镜像内的 `static/`，构建产物不提交 Git

## 注意

- `/token` 是现有服务端脚本调用接口，本次不改；`news-daily` 无需配套修改或重启
- SM4 一次性密钥为进程内缓存，生产必须保持 `THREADS=1`
- 生产部署由 Docker 多阶段构建执行 `npm ci && npm run build`，不需要上传或提交前端构建文件
