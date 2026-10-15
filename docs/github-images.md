# GitHub Actions 与容器镜像

推送 `main`、推送 `v*` 标签，或在 Actions 手动运行 **Build and publish container images**，会先检查前端构建，再并行构建、检查并发布三个 Linux amd64 镜像：

| 服务 | 镜像 |
| --- | --- |
| 前端 Nginx | `ghcr.io/bjwlxyzhuzhu/aibao-web:latest` |
| FastAPI | `ghcr.io/bjwlxyzhuzhu/aibao-api:latest` |
| 本地 ASR | `ghcr.io/bjwlxyzhuzhu/aibao-asr:latest` |

每个镜像同时保留 `sha-完整提交SHA` 标签；默认分支构建还生成 `main` 和 `latest`。版本标签构建生成对应 `v*` 标签。PR 只做构建检查，不发布镜像。各镜像仅在自身容器检查通过后推送；任一服务失败时应先查看日志，不能把另外两个服务的成功当成完整发布成功。

Actions 使用仓库内置 `GITHUB_TOKEN`，仅授予 `contents: read`、`packages: write`。不需要配置个人访问令牌，也不需要把模型密钥放进 Actions。第一次发布的 GHCR 包可能是私有的；可在 GitHub Packages 的 Package settings 中按需要改成 Public，或在服务器用只读包凭据执行 `docker login ghcr.io`。仓库公开不代表包一定公开。

## 服务器拉取运行

在仓库根目录执行：

```sh
cp .env.example .env
# 在服务器填写随机 DB_PASSWORD、JWT_SECRET、CHILD_KEY、DEMO_PASSWORD 和 LLM_API_KEY。
# DB_PASSWORD 建议仅用足够长的随机字母数字，避免数据库 URL 转义问题。
# DEMO_PASSWORD 是首次引导管理员/园长账号的密码，必须自行设置；首次登录后修改。
docker compose --env-file .env -f deploy/compose.images.yml pull
docker compose --env-file .env -f deploy/compose.images.yml up -d
docker compose --env-file .env -f deploy/compose.images.yml ps
```

默认只绑定 `127.0.0.1:8080`，由现有 HTTPS 反代接入。需要其他绑定地址时在 `.env` 设置 `WEB_BIND`、`WEB_PORT`。生产环境保持 `DEMO_MODE=false`、`SEED_DEMO=false`。首次 ASR 转写需下载模型权重，已缓存权重保存在 `asrmodels` 卷；CI 只验证依赖可导入和健康接口，不执行真实音频转写。

## 数据与初始化

本次发布按园方要求排除园徽、爱宝/星宝及其他卡通形象、议事场景图，构建出的镜像也不含这些图片。后台仍保留品牌与形象管理功能；公开版本的固定图片位置可能为空，完整品牌素材应在园方私有部署时另行提供，不要把空白图片区域当成服务启动失败。

公开代码与镜像不含园方真实教职工名单、初始密码表、本地 `.env`、数据库、上传文件或测试人脸照片。名单应部署后由园方管理员在导入中心上传。没有真实名单时，应用可初始化管理员、园长与基础制度；演示教师/家长账号需要对应班级和任职数据，不能假定代码自带完整园方数据。

## 发布与运行的区别

本流水线负责把代码发布为镜像，不会自动登录园方服务器、迁移业务数据库或更新现场服务。首次上线或升级由园方运行上述命令；更新前备份现有数据卷。若要回到某个构建，在 `.env` 设置 `IMAGE_TAG=sha-完整提交SHA` 后重新拉取启动。
