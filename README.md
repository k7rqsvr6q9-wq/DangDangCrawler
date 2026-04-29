# 当当网图书榜单爬虫系统

## 项目简介

当当网图书榜单爬虫系统是一款专业的图书市场数据采集工具。系统自动爬取当当网畅销榜和新书热卖榜数据，经过智能清洗后存储至MySQL数据库，并支持CSV导出。

**解决的核心问题**：当当网页面数据分散、格式不统一，手动收集效率极低。本系统实现了从数据采集、清洗到存储的全流程自动化，特别针对书名中混杂的营销文字、副标题等问题，设计了多策略分隔算法。

## 功能特性

- **多维度爬取**：支持畅销榜/新书热卖榜，覆盖24小时/7日/30日/月度/年度等时间维度
- **智能书名分隔**：多种策略从左到右扫描，自动分离书名与营销文字/副标题/版本信息
- **断点续爬**：根据数据库已有数据自动计算已爬页数，跳过已爬取的页面
- **详情页深度采集**：自动访问图书详情页，提取分类和出版时间
- **数据清洗**：创作者/出版社名称标准化，价格/折扣/评分合理性校验
- **MySQL持久化**：批次管理、数据去重（upsert）、批量删除
- **CSV导出**：支持字段选择，自定义导出内容
- **Web界面**：响应式布局、明暗主题切换、可拖拽分割面板、级联时间选择器
- **反爬策略**：随机User-Agent轮换、请求间隔随机化、重试递增等待

## 技术栈

| 类别   | 技术                                        |
| ---- | ----------------------------------------- |
| 语言   | Python 3.11+                              |
| 后端框架 | Flask                                     |
| 前端   | HTML + CSS + JavaScript（原生，无框架依赖）         |
| 数据库  | MySQL + SQLAlchemy ORM + PyMySQL          |
| 爬虫   | Requests + BeautifulSoup4 + lxml          |
| 包管理  | uv + pyproject.toml                       |

## 环境准备与安装

### 前置条件

- Python 3.11 或更高版本
- MySQL 5.7+ 或 8.0+（需已启动服务）
- [uv](https://docs.astral.sh/uv/) 包管理器

### 安装步骤

1. **克隆项目**

```bash
git clone <项目仓库地址>
cd DangDangCrawler
```

1. **安装依赖**

```bash
uv sync
```

1. **配置数据库**

编辑项目根目录下的 `config.ini` 文件，填入你的MySQL连接信息：

```ini
[database]
host = localhost
port = 3306
username = root
password = 你的密码
database = dangdang_data
```

> ⚠️ 请勿将包含真实密码的config.ini提交到版本控制系统

1. **启动应用**

```bash
uv run python main.py
```

启动后自动打开浏览器访问 `http://127.0.0.1:5000`

1. **初始化数据库**

在Web界面点击「初始化数据库」按钮，系统将自动创建数据库和表结构。

## 运行与使用

### 基本使用流程

1. **选择榜单类型**：畅销榜 或 新书热卖榜
2. **选择时间范围**：最近（24小时/7日/30日）、今年月度、往年年度
3. **设置页码范围**：起始页和结束页（每页20本书，最多25页）
4. **勾选断点续爬**（可选）：跳过数据库中已保存的页面
5. **点击"开始爬取"**：观察进度条和实时数据
6. **保存到数据库**：爬取完成后点击"保存数据"
7. **导出CSV**：选择需要的字段后导出

### 配置说明

所有配置集中在 `config.ini`，修改后重启生效：

```ini
[spider]
request_interval_min = 1.0    # 请求最小间隔（秒）
request_interval_max = 3.0    # 请求最大间隔（秒）
retry_count = 3               # 失败重试次数
timeout = 30                  # 请求超时时间（秒）

[server]
host = 127.0.0.1              # Web服务监听地址
port = 5000                   # Web服务端口
debug = false                 # 调试模式
```

## 项目结构

```
Project_2_Dang/
├── main.py                          # 程序入口
├── config.ini                       # 配置文件（数据库/爬虫/服务器）
├── pyproject.toml                   # 项目依赖定义
│
├── dangdang_crawler/
│   ├── core/                        # 核心爬虫模块
│   │   ├── spider.py                # 爬虫引擎（HTTP请求、反爬、流程控制）
│   │   ├── parser.py                # HTML解析器（列表页+详情页）
│   │   ├── cleaner.py               # 数据清洗器（书名分隔、字段标准化）
│   │   └── scheduler.py             # 任务调度器（异步执行、暂停/恢复）
│   ├── database/                    # 数据库模块
│   │   ├── models.py                # ORM模型（BookRanking表定义）
│   │   └── connector.py             # 数据库连接器（CRUD、断点续爬）
│   ├── web/                         # Web界面模块
│   │   ├── app.py                   # Flask后端API
│   │   └── templates/
│   │       └── index.html           # 前端界面（单页应用）
│   └── utils/                       # 工具模块
│       ├── config.py                # 配置管理（读取config.ini）
│       ├── logger.py                # 日志系统（控制台+文件轮转）
│       └── helpers.py               # 工具函数（URL构建、批次ID、UA轮换）
```

## API接口

| 方法   | 路径                  | 说明             |
| ---- | ------------------- | -------------- |
| POST | `/api/start`        | 启动爬取任务（支持断点续爬） |
| POST | `/api/stop`         | 停止爬取           |
| POST | `/api/pause`        | 暂停/恢复爬取        |
| GET  | `/api/status`       | 获取爬取状态和实时数据    |
| POST | `/api/save_db`      | 保存爬取数据到数据库     |
| POST | `/api/init_db`      | 初始化数据库和表结构     |
| GET  | `/api/db_status`    | 查询数据库连接状态      |
| GET  | `/api/batches`      | 获取所有批次列表       |
| GET  | `/api/batch_items`  | 获取指定批次数据       |
| POST | `/api/delete_batch` | 删除指定批次         |
| POST | `/api/export_csv`   | 导出CSV文件        |

## 注意事项

1. 请求间隔建议1-3秒，避免触发当当网反爬机制
2. 当当网页面编码为GBK，系统已自动处理编码检测
3. 数据库为可选项，不配置也可使用爬取和导出功能
4. `config.ini` 中包含数据库密码，请勿提交到公开仓库
5. 每页固定20本书，断点续爬据此计算已爬页数

## 许可证

© 2026 DangDang Crawler Project
