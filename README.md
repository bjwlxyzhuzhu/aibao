# 爱宝园务大脑

幼儿园保教治理“对抗—协同”多智能体系统，提供园长、教职工、家长与管理员界面。

## 功能与目录

- `api/`：FastAPI 后端，包含保教巡查、家园沟通、园务议事和脱敏处理。
- `web/`：React、TypeScript、Vite 前端与三维议事回放。
- `asr/`：本地语音识别服务。
- `assets/`、`web/public/`：经园方授权公开的园徽、爱宝/星宝、其他卡通角色与卡通议事场景。
- `deploy/`：容器部署配置。
- `.github/workflows/images.yml`：自动构建、检查并发布容器镜像。

AI 提供辅助建议，最终业务决定由有权限的人员审核确认。

## 自动构建

推送到 `main` 后，GitHub Actions 自动检查前端构建，并构建、验证、发布 `web`、`api`、`asr` 三个容器镜像。

详见 [镜像使用说明](docs/github-images.md)，构建结果见 [Actions](https://github.com/bjwlxyzhuzhu/aibao/actions)。

## 公开资源范围

园徽和卡通素材已获得园方公开上传授权。仓库及镜像不包含真实人员名单、业务数据库、个人照片、上传文件或实际访问密钥。原始加工图不在本次素材发布范围内。
