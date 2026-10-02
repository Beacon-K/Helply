# Helply — 小微企业 IT 服务台

Fanshawe College BIA Capstone 项目。基于 **Django 6.1**（作为依赖使用，不修改框架源码），PostgreSQL，Docker。

## 快速开始

### 在新电脑上安装（只需一次）

前提：已安装 **Python 3.12 或以上版本**，并且能联网。Windows 安装 Python 时记得勾选 "Add python.exe to PATH"。

- **Windows**：双击 `setup.bat`
- **macOS / Linux**：在终端运行 `./setup.sh`

脚本会自动创建虚拟环境、安装 Django、建立数据库并导入演示数据。

> 注意：`.venv` 文件夹绑定了创建它的那台电脑，不能直接拷贝到别的电脑上使用。换电脑时请重新运行安装脚本。

### 运行演示

- **Windows**：双击 `start-demo.bat`
- **macOS / Linux**：运行 `./start-demo.sh`

脚本会刷新演示数据（**会删除全部工单并重新生成**），然后启动服务器并打开 http://127.0.0.1:8000 。

如果不想刷新数据，直接启动即可：

```bash
.venv\Scripts\python.exe manage.py runserver      # macOS / Linux: .venv/bin/python manage.py runserver
```

### 数据库

- **默认使用 SQLite**，不需要任何配置。
- **开发用 PostgreSQL**（推荐，和正式部署一致）：
  1. 启动 Docker Desktop
  2. 复制 `.env.example` 为 `.env`，并改掉里面的 `POSTGRES_PASSWORD`（`.env` 不会提交到 git）
  3. `docker compose up -d db` 启动数据库容器，端口只对本机开放
  4. `python manage.py migrate`，然后 `python manage.py seed_demo --reset`

  `start-demo.bat` 检测到 `.env` 里配置了 PostgreSQL 时，会自动启动数据库容器。
- 删掉 `.env` 里的 `POSTGRES_*` 这几行，就会切换回 SQLite。

### Docker（PostgreSQL）

```bash
docker compose up --build
docker compose exec web python manage.py seed_demo
```

Docker 使用 `requirements-docker.txt`，其中额外包含 PostgreSQL 驱动和 gunicorn；本地运行只需要 `requirements.txt`。

### 演示账号

演示账号的统一密码写在 `apps/core/management/commands/seed_demo.py` 的 `DEMO_PASSWORD` 里，**仅限开发和演示使用**。

| 用户名 | 角色 | 说明 |
|---|---|---|
| alice | Supervisor 主管 | 同时拥有 /admin 权限 |
| tom | Technician 技术员 | Service Desk、Applications 组 |
| tina | Technician 技术员 | Service Desk、Network 组 |
| emma / eric | Employee 员工 | 提交工单 |

## 架构

```
config/            设置、URL 路由
apps/
  accounts/        用户（三种角色）、部门、支持组
  tickets/         工单、评论、审计事件、满意度回访
    choices.py     状态、ITIL 影响度×紧急度 优先级矩阵
    workflow.py    ★ 工单状态机（规则 + 权限 + 副作用）
    services.py    用例：提交 / 评论 / 回访
    selectors.py   行级数据权限（谁能看哪些工单）
  sla/             SLA 策略 + ★ SLA 引擎（到期计算、暂停/恢复、预警、违约检测）
  assets/          IT 资产台账
  kb/              知识库文章
  ai/              ★ AI 服务层（可插拔后端）+ AI 建议日志
  core/            角色化仪表盘、演示数据命令
```

### 工单生命周期

```
NEW → TRIAGED → ASSIGNED → IN_PROGRESS ⇄ ON_HOLD
                                │
                            RESOLVED → CLOSED（+ 满意度回访）
                                └→ reopen → IN_PROGRESS
NEW / TRIAGED / ASSIGNED → CANCELLED
```

| 动作 | 谁可以做 |
|---|---|
| triage / assign | 主管（或 AI 高置信度时自动完成） |
| start / hold / resume / resolve | 被分派的技术员（主管可代办） |
| reopen / close / cancel | 提单员工本人（close、cancel 主管也可） |

每一步都写入 `TicketEvent` 审计轨迹。

### AI 在业务流程中的位置

| 功能 | 触发点 | 当前实现 | 后续可替换为 |
|---|---|---|---|
| 自动分类 + 分诊 | 提交工单 | 关键词基线（`ai/backends/keyword.py`） | LLM / 微调分类器 |
| 自动分派 | 分类置信度 ≥ 阈值 | 组内负载最低的技术员 | 技能 + 负载 + 历史表现 |
| 相似工单推荐 | 工单详情（技术员） | Jaccard 文本相似度 | pgvector 向量检索 |
| 知识库问答 | KB 搜索 / 工单详情 | Jaccard 相似度 | RAG |
| SLA 预警 | 仪表盘 / `check_sla` | 规则：已用时间 ≥ 75% | 预测模型 |

所有 AI 输出都记录在 `AISuggestion`（置信度、是否自动应用、人工是否采纳），**可以量化 AI 准确率**。
切换后端只需修改 `HELPLY_AI_BACKEND` 设置，不用改业务代码。

### 知识库

- 文章以 Markdown 文件形式放在 `apps/kb/articles/`，**一篇文章一个文件**，文件名就是 URL slug，纳入 git 版本管理。
- 修改或新增文章后运行 `python manage.py seed_kb`，可以重复执行，只会新增或更新文章。
- 文件开头的元数据：`title`、`category`、`audience`（`everyone` 表示员工自助，`internal` 表示仅 IT 可见的操作手册）、`keywords`（同义词，用于提高搜索命中率）、`summary`。
- 正文支持：`##` 标题、`-` 列表、`1.` 步骤、`**粗体**`、`` `代码` ``、`>` 提示框。所有内容都会先做 HTML 转义，防止 XSS。

### SLA 定时检查

```bash
python manage.py check_sla      # 建议每 5 分钟跑一次（cron / 任务调度器）
```

> ⚠️ `seed_demo` 里的 SLA 时长（P1 15 分钟/4 小时 … P4 8 小时/72 小时）是占位值，需要和客户确认。
> 目前按 24×7 自然时间计算，尚未支持工作时间日历。

## 测试

```bash
python manage.py test
```
