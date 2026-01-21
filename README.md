# GitLab AI Review

一个基于PyQt6的GitLab Merge Request AI代码审查工具。

## 功能特性

- 📋 可视化浏览GitLab项目的Merge Request
- 🔍 差异(Diff)代码查看，支持语法高亮
- 🤖 AI驱动的自动代码审查
- 💾 本地缓存，支持离线查看
- 🎨 现代化的PyQt6界面

## 安装

### 1. 克隆项目

```bash
git clone <repository_url>
cd gitlab-ai-review
```

### 2. 创建虚拟环境

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

## 配置

### 配置方式

支持两种配置方式，推荐使用 `.env` 文件配置敏感信息：

| 方式 | 文件 | 用途 | 优先级 |
|------|------|------|--------|
| 环境变量 | `.env` | 敏感信息 (Token、API Key) | 高 |
| 配置文件 | `config.yaml` | 非敏感配置 (UI、审查规则等) | 低 |

### 方式一：环境变量 (推荐用于敏感信息)

```bash
# 复制示例文件
cp .env.example .env

# 编辑 .env 文件
```

```env
# GitLab 配置
GITLAB_URL=http://pd-gitlab.toppanecquaria.com:10080
GITLAB_TOKEN=glpat-your_token_here

# AI 配置
OPENAI_API_KEY=sk-your_key_here
```

### 方式二：配置文件

```bash
# 复制示例文件
cp config.example.yaml config.yaml

# 编辑 config.yaml 文件
```

配置文件支持更详细的设置，如 UI 布局、审查规则等。

## GitLab Token配置

在GitLab中创建Personal Access Token：

1. 访问 GitLab → Settings → Access Tokens
2. 创建新Token，勾选以下权限：
   - `api`
   - `read_api`
   - `read_repository`

## 使用

```bash
python main.py
```

## 项目结构

```
gitlab-ai-review/
├── main.py              # 应用入口
├── config.yaml          # 配置文件
├── requirements.txt     # 依赖
├── src/
│   ├── ui/             # PyQt界面模块
│   ├── gitlab/         # GitLab API集成
│   ├── ai/             # AI审查模块
│   ├── core/           # 核心业务逻辑
│   └── utils/          # 工具模块
└── tests/              # 测试
```

## 开发

```bash
# 运行测试
pytest

# 代码格式化
black src/
isort src/
```

## License

MIT
