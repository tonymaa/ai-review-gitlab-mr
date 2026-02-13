# GitLab AI Review 打包说明

本项目的打包方案将前端（React + Vite）和后端（Python FastAPI）打包成一个独立的 EXE 程序。

## 打包脚本说明

### 1. `build.bat` - 完整打包脚本（推荐）
生成包含所有依赖的目录结构，EXE 文件较小，启动较快。

**使用方法：**
```bash
build.bat
```

**输出：**
- `dist/GitLab-AI-Review/` - 完整分发目录
- `GitLab-AI-Review.exe` - 主程序（复制到项目根目录）

---

### 2. `build-quick.bat` - 快速打包
适用于前端已构建的情况，快速重新打包。

**使用方法：**
```bash
build-quick.bat
```

**前提条件：** 前端必须已构建（`web/dist` 目录存在）

---

### 3. `build-onefile.bat` - 单文件打包
生成单个 EXE 文件，包含所有依赖。文件较大，但分发方便。

**使用方法：**
```bash
build-onefile.bat
```

**输出：**
- `GitLab-AI-Review.exe` - 单文件可执行程序

---

## 环境要求

### 必需软件：
1. **Python 3.10+** - 后端运行环境
2. **Node.js 18+** - 前端构建环境
3. **Git** - 版本控制（可选）

### Python 依赖：
```bash
pip install -r requirements.txt
pip install pyinstaller
```

### 前端依赖：
```bash
cd web
npm install
```

---

## 手动打包步骤

如果你想手动控制打包过程：

```bash
# 1. 构建前端
cd web
npm run build
cd ..

# 2. 安装 PyInstaller（如果还没安装）
pip install pyinstaller

# 3. 使用单文件配置打包
cd build
pyinstaller --clean onefile.py
```

---

## 打包后运行

打包完成后，直接运行 EXE 文件：

```bash
GitLab-AI-Review.exe
```

程序将自动：
1. 启动 FastAPI 后端服务器（默认端口 19000）
2. 打开浏览器访问 http://localhost:19000

---

## 常见问题

### 1. 打包后文件过大
- 单文件打包通常在 80-150MB
- 这是正常的，因为包含了 Python 解释器和所有依赖
- 可以使用 UPX 压缩来减小体积（在 spec 文件中已启用）

### 2. 杀毒软件误报
- PyInstaller 打包的程序可能被误报为病毒
- 可以添加到白名单或使用数字签名

### 3. 前端页面无法加载
- 检查 `web/dist` 目录是否正确构建
- 确认 spec 文件中的 datas 配置正确

### 4. API 请求失败
- 检查后端服务是否正常启动
- 查看控制台输出的日志信息

---

## 自定义配置

### 修改端口号
编辑 `server.py` 或 `server/main.py`，修改默认端口。

### 添加应用图标
1. 准备一个 `.ico` 格式的图标文件
2. 放在项目根目录，命名为 `icon.ico`
3. 在 spec 文件中取消注释 `icon='icon.ico'`

### 隐藏控制台窗口
在 spec 文件中将 `console=True` 改为 `console=False`

---

## 文件结构

```
gitlab-ai-review/
├── build.bat              # 完整打包脚本
├── build-quick.bat        # 快速打包脚本
├── build-onefile.bat      # 单文件打包脚本
├── build/
│   └── onefile.py         # PyInstaller 单文件配置
├── server/                # 后端源码
├── src/                   # 核心模块
├── web/                   # 前端源码
│   └── dist/              # 前端构建产物
└── server.py              # 后端入口
```
