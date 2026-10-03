# Helply — 小微企业 IT 服务台

Fanshawe College BIA Capstone 项目。基于 **Django 6.1**（作为依赖使用，不修改框架源码），PostgreSQL，Docker。

## 快速开始

### 在新电脑上安装（每台电脑只需一次）

前提：已安装 **Python 3.12 或以上版本**，并且能联网。Windows 安装 Python 时记得勾选 "Add python.exe to PATH"。

- **Windows**：双击 `setup.bat`
- **macOS / Linux**：在终端运行 `./setup.sh`

### 放在外接硬盘上、在多台电脑之间使用

项目可以放在外接硬盘上，插到不同电脑上运行：

- **每台电脑有自己的虚拟环境**：`.venv-电脑名`，例如 `.venv-KAI-ROG`。虚拟环境只能配合创建它的那台电脑上的 Python 使用，所以每台电脑**第一次使用前运行一次 `setup.bat`**，之后就不用再装了。
- **盘符无所谓**：脚本全部使用相对路径，硬盘插上后不管变成 D:、E: 还是别的盘都能运行。
- **数据库**：`.env` 里配置了 PostgreSQL 时，如果这台电脑的 Docker Desktop 正在运行，就使用 PostgreSQL；如果没有 Docker，**会自动改用硬盘上的 SQLite**，保证一定能运行。PostgreSQL 的数据保存在各台电脑自己的 Docker 里，不在硬盘上；演示数据可以随时用 `seed_demo --reset` 重新生成。

### 运行演示

- **Windows**：双击 `start-demo.bat`
- **macOS / Linux**：运行 `./start-demo.sh`

脚本会刷新演示数据（**会删除全部工单并重新生成**），然后启动服务器并打开 http://127.0.0.1:8000 。

如果不想刷新数据，直接启动即可：

```bash
.venv\Scripts\python.exe manage.py runserver      # macOS / Linux: .venv/bin/python manage.py runserver
```

### 生产环境（真实使用）

演示和生产严格分开：

| | 演示 | 生产 |
|---|---|---|
| `.env` 设置 | 不设置，或 `HELPLY_ENVIRONMENT=demo` | `HELPLY_ENVIRONMENT=production` |
| 安装 | `setup.bat` 导入演示数据 | `setup.bat` 生成私有密钥、初始化分类/SLA/知识库，并创建第一个主管账号，**不导入任何演示数据** |
| 启动 | `start-demo.bat` / `start-online.bat`，会重置演示数据 | `start-production.bat`，**从不删除或修改业务数据** |
| 演示命令 | 可用 | `seed_demo`、`seed_tickets`、`demo_passwords` 全部**拒绝执行**；另外只要数据库里有非演示账号，也会拒绝清空数据 |

**部署步骤：**

1. 准备一台 24 小时开机的电脑或服务器，建议使用 PostgreSQL（见上方"数据库"）。
2. 复制 `.env.example` 为 `.env`，设置 `HELPLY_ENVIRONMENT=production`，并填写邮件服务器（`DJANGO_EMAIL_BACKEND`、`EMAIL_*`）和 `HELPLY_SITE_URL`。
3. 运行 `setup.bat`：生成私有的 `DJANGO_SECRET_KEY`，建表，运行 `init_helply` 创建第一个主管账号。
4. 运行 `start-production.bat`：自动检查配置、应用数据库更新，启动定时任务和 Web 服务器；如果 `.env` 里有 `CLOUDFLARE_TUNNEL_TOKEN`，同时连接隧道。
5. 主管登录后，在 **Admin → Users** 里添加员工和技术员。

**自动运行的内容：** 每 5 分钟检查 SLA 并发出预警、跟进已解决但未确认的工单；**每天自动备份数据库**到 `backups/`，保留最近 14 份。错误日志写入 `logs/helply.log`。

**常用命令：** `python manage.py backup_db`（立即备份）、`python manage.py seed_kb --overwrite`（用原稿覆盖知识库文章，慎用）、`python manage.py check --deploy`（检查生产配置）。

### 公网演示（https://helply.work）

用 Cloudflare Tunnel 把本机的 Helply 发布到 `https://helply.work`：电脑主动连接到 Cloudflare，**不需要开放任何端口**，在学校 Wi-Fi、手机热点等任何网络下都能用，HTTPS 证书由 Cloudflare 自动提供。

**一次性设置（在 Cloudflare 后台完成）：**

1. 登录 Cloudflare → **Zero Trust** → **Networks → Tunnels** → **Create a tunnel**，类型选 **Cloudflared**，名字填 `helply`。
2. 安装连接器那一页会显示一条命令，复制其中 `--token` 后面的那一长串字符。
3. 打开本项目的 `.env` 文件，粘贴到 `CLOUDFLARE_TUNNEL_TOKEN=` 后面并保存。**这个令牌相当于隧道的钥匙，不要发给别人，也不要提交到 git。**
4. 回到 Cloudflare，添加 **Public Hostname**：Subdomain 留空，Domain 选 `helply.work`，Service 选 **HTTP**，URL 填 `localhost:8000`，保存。

（Cloudflare 后台的菜单名称可能会随版本调整，以实际界面为准。）

**每次演示：** 双击 `start-online.bat`。它会：

- 刷新演示数据（**会删除全部工单并重新生成**）；
- 用正式的 Web 服务器 Waitress 运行，关闭调试页面，只监听本机 `127.0.0.1`；
- **给每个演示账号生成一个新的随机密码**，显示在窗口里，同时保存到 `demo-passwords.txt`（不会提交到 git）；
- 连接隧道，然后就可以通过 `https://helply.work` 访问。

关掉窗口即下线。下次用 `start-demo.bat` 在本机演示时，账号会恢复成 `.env` 里的共享密码。

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

演示账号的统一密码保存在本地的 `.env` 文件里（`HELPLY_DEMO_PASSWORD`），**不在代码里，也不会提交到 git**。第一次导入演示数据时如果还没有设置，会自动生成一个随机密码写进 `.env`。所有密码在数据库里都是加密存储的。

| 用户名 | 角色 | 说明 |
|---|---|---|
| alice | Administrator 管理员 | IT 负责人，同时拥有 /admin 后台权限 |
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

### 云服务器监控

左侧栏 **Cloud servers**（仅 IT 人员可见）。每台 VPS 安装一个轻量 agent（`agent/helply_agent.py`，Python + psutil），每 10 秒通过 HTTPS 上报 CPU、内存、磁盘、网络、负载和运行时长。

| 要点 | 说明 |
|---|---|
| 只读 | agent 只上报数据，不开端口、不接受命令；令牌泄露最多只能伪造这一台的读数 |
| 令牌 | 每台服务器一个，数据库只存 SHA-256 哈希；只在创建时显示一次，可随时重新生成 |
| 接入 | 点 **Add server**（不用填任何信息）→ 在服务器上运行页面给出的一行命令 → agent 首次上报时自动识别主机名、系统、CPU/内存/磁盘、公网 IP、云服务商、地区和机型，并填好服务器信息。费用、续费、负责人在接入后可选填。Linux 装成 systemd 服务（低权限用户），Windows 装成计划任务（LOCAL SERVICE），卸载用 `--uninstall` / `-Uninstall`；超过 24 小时未接入的占位服务器会被自动清理 |
| 告警转工单 | 离线 > 2 分钟、CPU/内存持续 5 分钟 ≥ 90%、磁盘 ≥ 90% → 自动建工单（分类 Servers & Cloud）、分派给负责人、启动 SLA；恢复后在工单里留记录，由技术员确认原因后再解决 |
| 维护模式 | 暂停告警 1/4/24 小时：告警照常记录，但不建工单 |
| 资产联动 | 每台服务器自动在资产台账生成一条 `VPS-xxxx` 记录（年费、续费日期） |
| 数据保留 | 原始读数 48 小时，每小时汇总保留 90 天（`HELPLY_MONITOR_*` 环境变量可调） |
| 定时任务 | 生产环境：`start-production.bat` 会运行 `monitor_check --every 30`（离线检测和数据汇总）；`run_jobs` 也会顺带执行一次 |
| 只显示真实服务器 | 页面只显示管理员添加并接入 agent 的服务器，演示数据不会生成任何服务器；没有服务器时显示接入引导。`start-demo.bat` / `start-online.bat` 也会运行 `monitor_check` 做离线检测 |

服务器必须能访问 Helply 的公网地址（例如 https://helply.work），在 `127.0.0.1` 上打开 Helply 时生成的安装命令用不了。

## 测试

```bash
python manage.py test
```
