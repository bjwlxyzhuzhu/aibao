# 容器镜像使用说明

## 镜像地址

| 服务 | 镜像 |
| --- | --- |
| Web | `ghcr.io/bjwlxyzhuzhu/aibao-web:latest` |
| API | `ghcr.io/bjwlxyzhuzhu/aibao-api:latest` |
| ASR | `ghcr.io/bjwlxyzhuzhu/aibao-asr:latest` |

## 自动构建

向 `main` 推送代码、推送 `v*` 标签，或手动运行 **Build and publish container images**，会触发构建。镜像在各自的容器检查通过后发布；PR 只检查构建，不发布镜像。镜像同时保留提交版本标签，便于选择版本。

Actions 使用 GitHub 自动提供的短期令牌，不需要把个人访问令牌或模型密钥提交到仓库。

## 拉取与运行

在部署机器准备本地环境配置后，从仓库根目录执行：

```sh
docker compose --env-file .env -f deploy/compose.images.yml pull
docker compose --env-file .env -f deploy/compose.images.yml up -d
docker compose --env-file .env -f deploy/compose.images.yml ps
```

环境配置格式见 `.env.example`。实际配置仅保存在部署机器，不要提交到 GitHub。如镜像包为私有，部署机器需要相应的只读拉取权限。

## 素材与数据

经园方授权公开的园徽、爱宝/星宝、其他卡通角色和议事场景，随源码进入新镜像。真实人员资料、业务数据库、上传内容及实际凭据不会进入镜像。语音识别模型权重由服务按需取得；CI 只验证依赖和健康接口，不执行真实音频转写。

流水线发布容器镜像，服务器更新由部署人员执行。更新已有服务前应备份持久化数据。
