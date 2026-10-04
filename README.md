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
- **数据库**：`.env` 里配置了 PostgreSQL 时，如果这台电脑的 Docker Desktop 正在运行，就使用 PostgreSQL；如果没有 Docker，**会自动改用硬盘上的 SQLite**，保证一定能运行。PostgreSQL 的数据保存在各台电脑自己的 Docker 里，不在硬盘上；演示数据只在数据库为空时自动生成；想有意清空重来，运行 `reset-demo.bat`。

### 运行演示

- **Windows**：双击 `start-demo.bat`
- **macOS / Linux**：运行 `./start-demo.sh`

脚本**不会改动你的数据**：只有数据库里一个用户都没有时才生成演示数据；然后启动服务器并打开 http://127.0.0.1:8000 。想有意清空演示、重新开始，运行 `reset-demo.bat`（需要输入 RESET 确认）。

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
| 启动 | `start-demo.bat` / `start-online.bat`，**不改动数据**（只在数据库为空时生成演示数据） | `start-production.bat`，**从不删除或修改业务数据** |
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

**启动：** 双击 `start-online.bat`。它会：

- 应用数据库更新；数据库为空（全新安装）时才生成演示数据，**已有的工单、人员、密码、SLA 设置都不会被改动**；
- 用正式的 Web 服务器 Waitress 运行，关闭调试页面，只监听本机 `127.0.0.1`；
- 演示账号的初始密码只在**账号创建时**随机生成一次（每人一个），保存到 `demo-passwords.txt`（不会提交到 git），之后不会自动更换，用户自己改了就以用户为准；想统一换一批，运行 `python manage.py demo_passwords --rotate`；
- 连接隧道，然后就可以通过 `https://helply.work` 访问。

关掉窗口即下线，数据保留。同时会运行定时任务（SLA 检查、工单跟进、续费提醒、每日备份）和服务器离线检测。

### 邮件发送（Brevo）

Helply 通过 **Brevo 的 SMTP 中继**发信（工单通知、续费提醒、新人设置密码链接）。Brevo **只负责发**，不提供邮箱，也不能收信。

| 项目 | 说明 |
|---|---|
| 域名验证 | 在 Brevo 验证 `helply.work`（Automatic，一次性授权）。Cloudflare 里新增的记录全部是「DNS only」：TXT `helply.work`（根域名）值 `brevo-code:fde1a096546d9f25aaf06085895b35e7`；CNAME `brevo1._domainkey` → `b1.helply-work.dkim.brevo.com`；CNAME `brevo2._domainkey` → `b2.helply-work.dkim.brevo.com`；TXT `_dmarc` 值 `v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com`；品牌链接 CNAME `em`、`r.em`、`img.em`。以上记录已核对生效。没有 SPF 记录是正常的，Brevo 用自己的退信域名通过 SPF。（这些是公开的 DNS 值，不是密钥） |
| SMTP 配置 | 写进 `.env`（模板见 `.env.example`）：`DJANGO_EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`、`EMAIL_HOST=smtp-relay.brevo.com`、`EMAIL_PORT=587`、`EMAIL_USE_TLS=true`、`EMAIL_HOST_USER`、`EMAIL_HOST_PASSWORD`（Brevo SMTP key）、`DEFAULT_FROM_EMAIL=Helply IT Service Desk <helpdesk@helply.work>`、`HELPLY_SITE_URL=https://helply.work`。登录名和 key 只放 `.env`，不进聊天、不进 git |
| 测试 | `python manage.py sendtestemail 你的真实邮箱`。免费档约每天 300 封 |
| 假域名保护 | **不会往保留域名发信**：`example.com`、`example.org`、`example.net`，以及以 `.example`、`.test`、`.invalid`、`.localhost` 结尾的地址（RFC 2606 / 6761）。这些地址不可能送达，退信会拉低 `helply.work` 的发信信誉，甚至导致 Brevo 封号。站内通知照常显示，日志里记一行 `reserved test domain`。People 页新增这类地址的人时，页面会提示「没有发邮件」，并照常显示一次性链接。要屏蔽更多占位域名，在 `.env` 里设置 `HELPLY_EMAIL_BLOCKED_DOMAINS=域名1,域名2`（在默认列表之外追加） |
| 收信 | 计划用 **Cloudflare Email Routing** 把 `support@helply.work` 转发到个人邮箱（免费）。用户的完整邮箱（Zoho、Google Workspace、Microsoft 365）不在本项目范围内 |

> **演示账号的邮箱是 `用户名@helply.work`。** `helply.work` 本身没有邮箱，由 Cloudflare Email Routing 的 Catch-all 规则把所有 `@helply.work` 邮件转发到管理员的一个真实邮箱（2026-10-03 已验证）。所以演示账号的**邮件通知默认关闭**（站内通知照常）：100 个账号的通知全涌进同一个收件箱没有意义，也会很快用完 Brevo 每天约 300 封的额度。演示邮件时只给少数账号打开（现在是 alice、tom、tina、sam）：用该账号登录，在「通知」页面打开邮件通知。`python manage.py demo_emails` 可以把仍是空白或 `@example.com` 的账号统一改成 `用户名@helply.work`（真实邮箱不会被动）。
>
> **Brevo 黑名单**：Brevo 对出现过硬退信的收件地址会自动拉黑，之后日志显示 `Blocked: due to blacklist user`，邮件根本不会发出。给一个新域名的地址发信之前，先确认它能收信（MX 和转发规则已生效），否则会被拉黑；被拉黑的地址在 Brevo 的 Transactional → Settings → Blocked contacts（或 Contacts → Blocklist）里移除。另外 Brevo 的「授权 IP」限制（Security → Authorized IPs）已对 SMTP key 关闭，因为这台服务器的出口 IP 会变；SMTP key 是唯一凭据，只放 `.env`，约 2027-10-03 到期，连续 90 天不用也会失效。

> 注意：Django 自带的「忘记密码」邮件（登录页链接）不经过上面的保护。演示账号用的是 `@example.com`，如果有人在登录页对这些账号点「忘记密码」，Django 会尝试发送；真实员工用真实邮箱不受影响。
### 数据库

- **默认使用 SQLite**，不需要任何配置。
- **开发用 PostgreSQL**（推荐，和正式部署一致）：
  1. 启动 Docker Desktop
  2. 复制 `.env.example` 为 `.env`，并改掉里面的 `POSTGRES_PASSWORD`（`.env` 不会提交到 git）
  3. `docker compose up -d db` 启动数据库容器，端口只对本机开放
  4. `python manage.py migrate`，然后 `python manage.py seed_demo --if-empty`

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
