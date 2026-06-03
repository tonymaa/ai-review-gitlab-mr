# GitLab AI Review

[English](./README.md) | **简体中文**

> 基于 AI 的 GitLab Merge Request 代码审查工具

GitLab AI Review 通过集成 AI 服务（OpenAI / Ollama），自动分析 MR 代码变更并生成智能审查意见。提供 Web 应用（FastAPI + React）和桌面应用（PyQt6）两种使用方式。

## 功能特性

- 可视化浏览 GitLab 项目和 MR 列表
- 代码差异查看，支持语法高亮
- AI 驱动的智能代码审查，支持自定义审查规则
- 直接在 MR 中发布评论、批准/取消批准
- SQLite 本地缓存，提升访问速度
- 多用户支持，JWT 身份认证
- 支持 Docker 部署

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.10+ / FastAPI / Uvicorn |
| 前端 | React 19 / TypeScript / Ant Design / Vite |
| 桌面端 | PyQt6 |
| 数据库 | SQLite |
| AI | OpenAI API / Ollama（本地模型） |

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/tonymaa/ai-review-gitlab-mr.git
cd ai-review-gitlab-mr
```

### 2. 后端设置

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

pip install -r requirements.txt
```

### 3. 前端设置

```bash
cd web
npm install
```

### 4. 配置

将 `.env.example` 复制为 `.env`，填入你的凭证：

```env
GITLAB_URL=https://gitlab.example.com
GITLAB_TOKEN=glpat-your_token_here

# 选择一种 AI 服务
OPENAI_API_KEY=sk-your_key_here
# OLLAMA_BASE_URL=http://localhost:11434
```

也可以使用 `config.example.yaml` 进行更详细的配置（AI 审查规则、自动刷新、UI 布局等）。

### 5. 获取 GitLab Token

在 GitLab 中前往 **Settings → Access Tokens** 创建令牌，所需权限：`api`、`read_api`、`read_repository`。

## 启动方式

### Web 应用（推荐）

```bash
# 开发模式（自动重载）
python server.py --reload

# 生产模式
python server.py --host 0.0.0.0 --port 19000
```

后端默认运行在 `http://127.0.0.1:19000`。开发时可单独启动前端：

```bash
cd web && npm run dev    # http://localhost:5173（自动代理 API 请求）
```

生产环境下，构建前端后由 FastAPI 提供静态文件服务：

```bash
cd web && npm run build
cd .. && python server.py --host 0.0.0.0 --port 19000
```

### 桌面应用

```bash
python main.py
```

### Docker 部署

```bash
cp .env.example .env   # 编辑填入你的凭证
docker-compose up -d
```

访问地址：`http://localhost:19000`。数据持久化目录：`./data`、`./cache`、`./logs`。

## API 接口

服务器运行后可访问交互式文档：`http://127.0.0.1:19000/docs`

| 分组 | 接口 |
|------|------|
| 认证 `/api/auth` | `POST /register`、`POST /login`、`POST /logout`、`GET /me` |
| GitLab `/api/gitlab` | `POST /connect`、`GET /projects`、`GET /projects/{id}/merge-requests`、`GET /merge-requests/{iid}/diff`、`GET/POST/DELETE .../notes`、`POST .../approve`、`POST .../unapprove` |
| AI 审查 `/api/ai` | `POST /review`、`GET /review/{task_id}`、`POST /review/file` |
| 配置 `/api/config` | `GET /config`、`POST /config` |
| 健康检查 | `GET /api/health` |

## 项目结构

```
ai-review-gitlab-mr/
├── server.py              # Web 服务器入口
├── main.py                # 桌面应用入口
├── config.example.yaml    # 配置模板
├── .env.example           # 环境变量模板
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
│
├── server/                # FastAPI 后端
│   ├── main.py           # 应用创建与启动
│   ├── api/              # 路由处理（auth、config、gitlab、ai、health）
│   └── models/           # 数据模型（session）
│
├── src/                   # 核心业务逻辑
│   ├── core/             # 配置、数据库、认证、异常
│   ├── gitlab/           # GitLab API 客户端与模型
│   ├── ai/               # 审查器与提示词模板
│   └── ui/               # PyQt6 桌面端界面
│
├── web/                   # React 前端
│   ├── src/
│   │   ├── api/          # API 客户端
│   │   ├── components/   # 布局、DiffViewer、MRList、CommentPanel
│   │   ├── contexts/     # 应用上下文
│   │   └── types/        # TypeScript 类型
│   └── vite.config.ts
│
├── data/                  # SQLite 数据库
├── cache/                 # 响应缓存
└── logs/                  # 应用日志
```

## 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `GITLAB_URL` | GitLab 服务器地址 | `https://gitlab.example.com` |
| `GITLAB_TOKEN` | 个人访问令牌 | `glpat-xxxxxxxxxxxx` |
| `OPENAI_API_KEY` | OpenAI API 密钥 | `sk-xxxxxxxxxxxx` |
| `OLLAMA_BASE_URL` | Ollama 服务地址 | `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama 模型名称 | `codellama` |
| `ALLOW_REGISTRATION` | 是否允许注册 | `true` |

## 架构

```
浏览器 → React (Vite :5173) → FastAPI (:19000) → GitLab API
                                              → OpenAI / Ollama
                                              → SQLite
```

## 开发

```bash
# 后端
python server.py --reload    # 自动重载
pytest                       # 运行测试
black src/ server/           # 代码格式化
isort src/ server/           # 导入排序

# 前端
cd web
npm run dev                  # 开发服务器
npm run build                # 生产构建
npm run lint                 # 代码检查
```

## 许可证

MIT
