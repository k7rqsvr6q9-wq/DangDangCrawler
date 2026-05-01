# Analysis - 当当网2025年畅销榜数据分析

独立于爬虫主项目的数据分析模块，基于当当网畅销榜Top500数据，提供6个维度的可视化分析。

## 目录结构

```
analysis/
├── README.md                           # 本文件
├── visualization.ipynb                 # Jupyter Notebook 分析代码
├── 当当网2025年畅销榜深度分析报告.md   # 完整分析报告（图文并茂）
└── charts/                             # 图表输出
    ├── 01_分类势力范围.png
    ├── 02_价格排名关系.png
    ├── 03_价格评分热力图.png
    ├── 04_标题词云.png
    ├── 05_出版社实力雷达图.png
    └── 06_排名分层对比.png
```

## 快速开始

### 1. 安装依赖

```bash
# 在项目根目录执行
uv pip install pandas numpy matplotlib seaborn squarify wordcloud jieba pymysql sqlalchemy
```

### 2. 确保数据就绪

先运行爬虫采集数据到MySQL数据库：

```bash
cd ..
uv run python main.py
```

### 3. 启动分析

```bash
# 方式一：Jupyter Notebook（推荐）
uv run jupyter notebook visualization.ipynb

# 方式二：命令行执行并导出HTML
uv run jupyter nbconvert --execute --to html visualization.ipynb
```

## 六个分析维度

| # | 图表 | 类型 | 分析目标 |
|:-:|------|------|---------|
| 1 | 分类势力范围 | 树状图 | 各分类市场份额 |
| 2 | 价格-排名关系 | 散点图 | 价格、评论数与排名关系 |
| 3 | 价格-评分组合 | 热力图 | 黄金定价与评分区间 |
| 4 | 标题关键词 | 词云图 | 畅销书流量密码 |
| 5 | 出版社实力 | 雷达图 | 头部出版社多维度对比 |
| 6 | 排名分层对比 | 箱线图 | 不同层级图书特征差异 |

## Notebook 结构

| 步骤 | 内容 |
|------|------|
| 第一步 | 环境配置（字体、配色、库导入） |
| 第二步 | 数据加载（从MySQL读取） |
| 第三步 | Top10畅销书预览（格式化表格） |
| 第四步 | 数据预处理（价格/评分/排名分层） |
| 图1-6 | 六个可视化分析 |
| 末尾 | 关键指标统计摘要 |

## 数据库配置

Notebook 从项目根目录的 `config.ini` 读取数据库连接信息，无硬编码密码：

```ini
[database]
host = localhost
port = 3306
username = root
password = 你的密码
database = dangdang_data
```

## 中文显示

Notebook 内置多策略中文字体查找：

1. 直接查找系统字体路径（Windows/macOS/Linux）
2. 扫描 `fontManager` 中的中文字体
3. 尝试常见字体名称

如仍无法显示中文，手动指定字体路径：

```python
import matplotlib.font_manager as fm
fm.fontManager.addfont(r'C:\Windows\Fonts\msyh.ttc')
```

## 自定义分析

修改 Notebook 中的以下参数即可自定义：

```python
# 配色方案
C = ['#7EC8E3', '#98D8AA', ...]  # 马卡龙色系

# 图表分辨率
plt.rcParams['figure.dpi'] = 120  # 调高可获更清晰输出

# 出版社筛选阈值
if dat['count'] >= 5  # 修改最低上榜数量
```
