# 爱宝园务大脑 —— 幼儿园保教治理"对抗—协同"多智能体系统

宝鸡幼儿园自研 · 中国教育技术协会"AI+教育"创新应用技能大赛 · 基础教育组 · 赛道四（教育智能体创构与应用创新）

依据《爱宝园务大脑 PRD v1.4》开发。四个端（园长 / 教职工 / 家长 / 管理员）、三条链（保教巡查 / 家园沟通 / 园务议事）、12 个智能体，全部模型调用经过本地脱敏网关；AI 结论和整改单都由园长确认。

本次公开发布按要求不包含园徽和卡通角色图片，`assets/` 与 `web/public/` 仅保留目录结构。应用可在无图片资源时初始化；需要完整品牌展示时，请在私有部署中另行配置这些图片。真实人员名单、密钥和本地业务数据也不包含在仓库或镜像中。

## 目录

```
api/                 FastAPI 后端
  app/agents/        三条链编排：inspect_chain / parent_chain / council_chain；offline_rules 为离线规则引擎
  app/gateway/       脱敏网关：文字（姓名→代号、手机号/身份证/住址→占位、健康明细→类别）、照片（YuNet 人脸模糊 + 去 EXIF）
  app/kb/            知识库：PDF/Word → 按章、条切片（保留条款号）→ 检索
  app/importer/      导入中心：模板解析、红/黄/绿校验、快照回滚；园徽多尺寸与取色；吉祥物真人检测
  app/services/      校历单双周、在岗推算、工单时限与两级升级
  prompts/           12 个智能体的系统提示词（带版本号，即"提示词体系文档"）
  seed_data/         示例知识库（标"示例，待替换"）+ 园方导入模板（含真实姓名，不进参赛包）
  tests/test_smoke.py 端到端冒烟测试
web/                 React 18 + Vite + TS + Tailwind + react-three-fiber
  src/pages/principal 驾驶舱、保教巡查（复核/整改/工单）、园务议事、3D 对抗回放、知识库
  src/pages/staff     手机巡查端（三步提交、打码预览、对抗过程、申诉、整改回传、家长转人工、助手）
  src/pages/parent    家长端爱宝答疑
  src/pages/admin     初始化向导、导入中心、组织账号、学期任职轮换、作息课表、模型阈值、脱敏日志、时限规则、形象品牌
  src/scene/          3D 议事桌：纸片人 Billboard、发言气泡、质询/支持/引用光束、裁定托盘、置信度环、导演镜头、回放
assets/              园徽、爱宝与星宝（三视图 + 表情）、8 个原创动物占位形象（SVG）
asr/                 本地语音识别容器（SenseVoice-Small + FSMN-VAD），音频不出园
deploy/              nginx.conf、install.sh（检测 CPU/内存/磁盘/Docker 后启动）
scripts/             export_package.py（导出参赛代码包并扫描密钥）、gen_avatars.py、cutout_assets.py
```

## 本地开发（Windows / macOS / Linux）

```bash
cd api
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt      # macOS/Linux: .venv/bin/pip
.venv/Scripts/python -m uvicorn app.main:app --port 8000
```

```bash
cd web
npm install
npm run dev        # http://localhost:5173 ，/api 代理到 8000
```

首次启动自动：建表 → 预置四层组织架构与岗位 → 导入 `seed_data` 中的园方模板（67 名教职工、16 个班、20 周校历、作息、130 格单双周课表）→ 注册吉祥物与园徽 → 导入示例知识库 → 生成一组**演示数据**（`is_demo` 标记）。

演示模式（`DEMO_MODE=true`）登录页有一键体验按钮：园长 `yuanzhang`、大一班班长 `dayi_banzhang`、保育员 `dayi_baoyu`（岗位账号，自动指向导入名单中大一班的当期任职人）、管理员 `admin`、家长邀请码 `DA1A26`；演示密码见 `api/app/config.py` 的 `DEMO_PASSWORD`。**生产环境必须设 `DEMO_MODE=false`、`SEED_DEMO=false`**，导入名单时初始密码随机生成，首次登录强制修改。

## 接入通义千问

在 `api/.env`（服务器上）填写 `LLM_API_KEY`、`LLM_BASE_URL`（OpenAI 兼容，默认 tokenone.work，可切换阿里云百炼）。管理员端「模型与阈值」可做连通测试、按智能体切换 max / flash、调置信度阈值与对抗轮数。

未配置密钥或调用连续失败时，三条链自动降级为**离线规则引擎**（关键词 + 条款检索），界面上明确标注"离线规则引擎"。它只用于断网兜底和界面演示，判断质量远低于大模型，**参赛证据数据请在接入模型后用真实试用产生**。

## 服务器部署

GitHub Actions 自动构建和发布 `web`、`api`、`asr` 三个 GHCR 镜像，支持直接拉取部署。镜像地址、权限、初始化与更新命令见 [GitHub 镜像部署说明](docs/github-images.md)。

```bash
cp .env.example .env     # 填写 DB_PASSWORD、JWT_SECRET、CHILD_KEY、LLM_API_KEY
bash deploy/install.sh   # 检测配置；低于 4 核/8GB/50GB 时语音识别降级
```

服务：`db`（PostgreSQL 16 + pgvector 镜像）、`api`、`asr`、`web`（Nginx，8080 端口），由园方现有 HTTPS Nginx 反代到 8080。

## 测试

```bash
cd api && .venv/Scripts/python tests/test_smoke.py
```

覆盖：校历单双周（10 月 15 日 = 第六周双周）、照片人脸模糊、巡查链对抗与条款引用、安全卫生健康类 100% 进复核、发往模型的文字无教职工姓名、申诉→复核→整改下发（非园长无法下发）→回传→验收关闭、家长端自动答复与转教师、红队拦截高风险草稿、议事链四方交叉质询与简报、导入校验与回滚、知识库上传后可检索。人脸测试图放在 `api/tests/fixtures/faces.jpg`（不随代码包分发，缺失时跳过）。

## 导出参赛代码包

```bash
python scripts/export_package.py
```

自动排除 `.env`、数据库、上传文件、依赖目录、含真实教师姓名的园方模板，并扫描密钥，发现疑似密钥即中止。

## 与 PRD 的对应与当前进度

| PRD | 状态 |
| --- | --- |
| ① 巡查链 T1–T6、D2–D4 | 已实现：三步提交、环节与在岗教师自动带出、照片打码预览、对抗过程、引用条款原文、申诉、复核、整改确认/回传/验收、3D 回放 |
| D1 驾驶舱 | 已实现：热力图（环节 × 16 班）、闭环率、对抗前后误判率、超时工单、家长端统计、待办提醒；真实/演示数据可切换 |
| ② 家园链 F1–F3、T7 | 已实现：调度官转人工、只用公开知识、红队审查与改写一次、教师回复 |
| ③ 议事链 D6 | 已实现：四视角两轮 + 简报（保留分歧），园长记录决定 |
| 管理员 A0–A14 | 已实现主体；A7 邀请码、A11 形象管理、A13 升班向导为简版 |
| 工单时限 4.6 | 已实现：工作时间计时（跳过周末、夜间、校历外假期）、过半提醒、两级升级、延期一次、时间线 |
| 语音 T3 | 接口与本地 ASR 容器已就绪；本机未启动 ASR 时提示改用文字 |
| 向量检索 | 目前为字二元组 BM25；`EMBED_MODEL` 实测后可叠加向量（`llm/client.py` 已预留 embed） |
| 浏览器推送、学期轮换定时提醒、PDF 周报 | 站内提醒已实现；周报用浏览器打印导出 PDF；Web Push 与定时提醒待补 |
