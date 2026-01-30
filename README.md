# GitLab AI Review

> 一个基于 FastAPI + React 的 GitLab Merge Request AI 代码审查工具

## 项目简介

GitLab AI Review 是一个帮助开发者更高效地进行代码审查的工具，提供 Web 应用和桌面应用两种方式。通过集成 GitLab API 和 AI 服务（OpenAI/Ollama），它可以自动分析 Merge Request 的代码变更，生成智能化的审查意见。

### 技术栈

| 层级 | 技术栈 |
|------|--------|
| **后端** | Python 3.10+ / FastAPI / Uvicorn |
| **前端** | React 19 / TypeScript / Ant Design / Vite |
| **桌面端** | PyQt6 |
| **数据库** | SQLite |
| **AI** | OpenAI API / Ollama (本地模型) |

## 功能特性

- 📋 **可视化浏览** - 直观查看 GitLab 项目的 Merge Request 列表
- 🔍 **代码差异查看** - 支持 Diff 代码查看，语法高亮
- 🤖 **AI 智能审查** - 自动分析代码变更，生成审查意见
- 💬 **评论管理** - 在 MR 中发布评论、批准/取消批准
- 💾 **本地缓存** - 支持 SQLite 缓存，提升访问速度
- 🎨 **现代化界面** - Web 端基于 Ant Design，桌面端基于 PyQt6
- 👥 **多用户支持** - 支持用户注册、登录，独立的配置管理

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/tonymaa/ai-review-gitlab-mr.git
cd gitlab-ai-review
```

### 2. 后端设置

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 前端设置

```bash
# 进入前端目录
cd web

# 安装依赖
npm install
```

### 4. 配置

#### 方式一：环境变量（推荐用于敏感信息）

```bash
# 复制示例文件
cp .env.example .env

# 编辑 .env 文件，填入你的配置
```

```env
# GitLab 配置
GITLAB_URL=https://gitlab.example.com
GITLAB_TOKEN=glpat-your_token_here

# AI 配置（选择一种）
OPENAI_API_KEY=sk-your_key_here
# 或使用 Ollama
OLLAMA_BASE_URL=http://localhost:11434
```

#### 方式二：配置文件

```bash
# 复制示例文件
cp config.example.yaml config.yaml

# 编辑 config.yaml 文件
```

配置文件支持更详细的设置，如 AI 审查规则、自动刷新配置等。

### 5. 获取 GitLab Token

1. 访问 GitLab → **Settings** → **Access Tokens**
2. 创建新 Token，勾选以下权限：
   - `api`
   - `read_api`
   - `read_repository`

## 启动方式

### 方式一：完整 Web 应用（推荐）

**启动后端服务：**

```bash
# 开发模式（自动重载）
python server.py --reload

# 生产模式
python server.py --host 0.0.0.0 --port 19000
```

默认运行在 `http://127.0.0.1:19000`

**启动前端（开发模式）：**

```bash
cd web
npm run dev
```

前端开发服务器运行在 `http://localhost:5173`，API 请求会自动代理到后端。

**生产部署：**

```bash
# 构建前端
cd web
npm run build

# 启动后端（FastAPI 会自动提供前端静态文件）
cd ..
python server.py --host 0.0.0.0 --port 19000
```

### 方式二：仅 API 服务

```bash
python server.py --host 127.0.0.1 --port 19000
```

API 文档访问：`http://127.0.0.1:19000/docs`

### 方式三：桌面应用

```bash
python main.py
```

启动 PyQt6 桌面应用，提供原生 GUI 界面。

### 方式四：Docker 部署

**使用 Docker Compose（推荐）：**

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入你的 GitLab Token 和 OpenAI API Key

# 2. 启动服务
docker-compose up -d

# 3. 查看日志
docker-compose logs -f
```

访问地址：`http://localhost:19000`

**使用 Docker 命令行：**

```bash
# 构建镜像
docker build -t gitlab-ai-review .

# 运行容器
docker run -d \
  --name gitlab-ai-review \
  -p 19000:19000 \
  -e GITLAB_URL=https://gitlab.example.com \
  -e GITLAB_TOKEN=your_token_here \
  -e OPENAI_API_KEY=your_key_here \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/cache:/app/cache \
  -v $(pwd)/logs:/app/logs \
  gitlab-ai-review
```

**数据持久化：**

Docker 版本会将以下数据挂载到宿主机：
- `./data` - SQLite 数据库
- `./cache` - 本地缓存
- `./logs` - 应用日志

## API 接口

### 认证接口 `/api/auth`

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/auth/register` | POST | 用户注册 |
| `/api/auth/login` | POST | 用户登录 |
| `/api/auth/logout` | POST | 用户登出 |
| `/api/auth/me` | GET | 获取当前用户信息 |
| `/api/auth/verify-token` | POST | 验证 Token 有效性 |

### GitLab 接口 `/api/gitlab`

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/gitlab/connect` | POST | 连接 GitLab 账户 |
| `/api/gitlab/projects` | GET | 获取项目列表 |
| `/api/gitlab/projects/{id}/merge-requests` | GET | 获取项目的 MR 列表 |
| `/api/gitlab/merge-requests/{iid}/diff` | GET | 获取 MR 的代码差异 |
| `/api/gitlab/merge-requests/related` | GET | 获取与当前用户相关的 MR |
| `/api/gitlab/.../notes` | GET/POST/DELETE | 评论管理 |
| `/api/gitlab/.../approve` | POST | 批准 MR |
| `/api/gitlab/.../unapprove` | POST | 取消批准 MR |

### AI 审查接口 `/api/ai`

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/ai/review` | POST | 启动 AI 审查任务 |
| `/api/ai/review/{task_id}` | GET | 查询审查任务状态 |
| `/api/ai/review/file` | POST | 单文件代码审查 |

### 配置接口 `/api/config`

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/config/config` | GET | 获取当前配置 |
| `/api/config/config` | POST | 更新配置 |

### 其他接口

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/health` | GET | 健康检查 |

## 项目结构

```
gitlab-ai-review/
├── server.py              # Web 服务器启动入口
├── main.py                # 桌面应用入口（已废弃）
├── config.yaml            # 应用配置文件
├── config.example.yaml    # 配置示例文件
├── .env                   # 环境变量（敏感信息）
├── .env.example           # 环境变量示例
├── requirements.txt       # Python 依赖
├── Dockerfile             # Docker 镜像构建文件
├── docker-compose.yml     # Docker Compose 配置
├── docker-entrypoint.sh   # Docker 启动脚本
├── .dockerignore          # Docker 构建忽略文件
│
├── server/                # 后端服务器模块
│   ├── main.py           # FastAPI 应用创建和配置
│   ├── api/              # API 路由
│   │   ├── health.py     # 健康检查
│   │   ├── auth.py       # 认证接口
│   │   ├── config.py     # 配置管理
│   │   ├── gitlab.py     # GitLab 集成
│   │   └── ai.py         # AI 审查
│   └── models/           # 数据模型
│       └── session.py    # 会话管理
│
├── src/                   # 核心业务逻辑
│   ├── core/             # 核心功能
│   │   ├── config.py     # 配置管理
│   │   ├── database.py   # SQLite 数据库
│   │   ├── auth.py       # JWT 认证
│   │   └── exceptions.py # 自定义异常
│   ├── gitlab/           # GitLab 集成
│   │   ├── client.py     # GitLab API 客户端
│   │   └── models.py     # GitLab 数据模型
│   ├── ai/               # AI 审查
│   │   ├── reviewer.py   # AI 审查器
│   │   └── prompts.py    # AI 提示词模板
│   └── ui/               # PyQt6 UI 桌面端
│
├── web/                   # 前端 React 应用
│   ├── package.json      # 前端依赖配置
│   ├── vite.config.ts    # Vite 构建配置
│   ├── index.html        # HTML 入口
│   └── src/
│       ├── main.tsx      # React 入口
│       ├── App.tsx       # 主应用组件
│       ├── api/          # API 客户端
│       │   └── client.ts
│       ├── components/   # React 组件
│       │   ├── layout/   # 布局组件
│       │   ├── CommentPanel.tsx
│       │   ├── DiffViewer.tsx
│       │   ├── MRDetail.tsx
│       │   └── MRListPanel.tsx
│       ├── contexts/     # React Context
│       │   └── AppContext.tsx
│       └── types/        # TypeScript 类型
│           └── index.ts
│
├── cache/                 # 缓存目录
├── data/                  # SQLite 数据库目录
└── logs/                  # 日志目录
```

## 开发

### 后端开发

```bash
# 启动开发服务器（自动重载）
python server.py --reload

# 运行测试
pytest

# 代码格式化
black src/ server/
isort src/ server/
```

### 前端开发

```bash
cd web

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build

# 代码检查
npm run lint
```

## 环境变量说明

| 变量 | 说明 | 示例 |
|------|------|------|
| `GITLAB_URL` | GitLab 服务器地址 | `https://gitlab.example.com` |
| `GITLAB_TOKEN` | GitLab Personal Access Token | `glpat-xxxxxxxxxxxx` |
| `OPENAI_API_KEY` | OpenAI API Key | `sk-xxxxxxxxxxxx` |
| `OLLAMA_BASE_URL` | Ollama 服务地址 | `http://localhost:11434` |
| `OLLAMA_MODEL` | Ollama 模型名称 | `codellama` |
| `ALLOW_REGISTRATION` | 是否允许注册 | `true` |

## 数据流向

```
┌─────────────────┐
│   用户浏览器     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  React 前端     │  Vite 开发服务器 :5173
│  (Ant Design)   │
└────────┬────────┘
         │ API 调用（代理）
         ▼
┌─────────────────┐
│  FastAPI 后端   │  Uvicorn :19000
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌──────┐  ┌──────┐  ┌──────────┐
│ GitLab │  │ OpenAI │  │ SQLite  │
│  API  │  │ Ollama │  │ Database │
└──────┘  └──────┘  └──────────┘
```

## License

MIT
