"""
HTML解析模块：从当当网榜单页面和图书详情页提取结构化数据

本模块负责将原始HTML文本转换为结构化的BookItem对象，包含两个核心功能：
1. 列表页解析：从榜单页面批量提取图书基本信息（书名、价格、评论等）
2. 详情页解析：访问单本图书详情页，提取分类和出版时间等深层信息

设计要点：
- 使用lxml解析器，兼顾速度和容错能力
- 列表页和详情页分离解析，避免单次请求过重
- 多级回退策略：优先从链接提取，失败后从纯文本提取
- URL协议补全：当当网链接常省略"http:"前缀，需统一补全
"""

import re
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup, Tag

from dangdang_crawler.utils.helpers import generate_user_agent
from dangdang_crawler.utils.logger import LoggerManager

logger = LoggerManager().get_logger("parser")


@dataclass
class BookItem:
    """
    图书数据实体类，存储单本图书的全部信息

    使用dataclass而非普通class的原因：
    - 自动生成__init__、__repr__等样板方法，减少代码量
    - 支持逐步填充字段（先解析列表页基础信息，再从详情页补充分类/出版时间）
    - 类型注解清晰，便于IDE提示和静态检查

    字段说明:
        rank_position: 榜单排名位置（1-500）
        book_title: 书名（经清洗后的主标题）
        introduction: 介绍/副标题（从原始标题中分离出的营销语或副标题）
        author: 创作者（可能包含多位作者，中文逗号分隔）
        publisher: 出版社名称
        publish_date: 出版时间，格式"YYYY-MM"
        current_price: 当前售价（元）
        original_price: 原价/定价（元）
        discount: 折扣率，如7.5表示7.5折（即75%）
        comment_count: 评论总数
        rating: 好评度百分比，如98.5表示98.5%
        category: 图书分类（如"小说"、"历史"等，从详情页提取）
        detail_url: 图书详情页完整URL
        cover_image: 封面图片完整URL
    """
    rank_position: int = 0
    book_title: str = ""
    introduction: Optional[str] = None
    author: Optional[str] = None
    publisher: Optional[str] = None
    publish_date: Optional[str] = None
    current_price: Optional[float] = None
    original_price: Optional[float] = None
    discount: Optional[float] = None
    comment_count: Optional[int] = None
    rating: Optional[float] = None
    category: Optional[str] = None
    detail_url: Optional[str] = None
    cover_image: Optional[str] = None


class DangDangParser:
    """
    当当网页面解析器，负责从HTML中提取图书数据

    解析策略分为两层：
    1. 列表页解析（parse_page）：从榜单ul.bang_list中批量提取图书信息
    2. 详情页解析（fetch_detail_info）：访问单本图书页面，提取分类和出版时间

    当当网页面结构特点：
    - 榜单页面使用ul.bang_list > li结构，每个li代表一本书
    - 作者和出版社分别在两个div.publisher_info中
    - 好评度通过CSS width百分比表示（如width:98%）
    - 链接常省略协议前缀（如"//product.dangdang.com/..."）
    """

    def parse_page(self, html: str) -> list[BookItem]:
        """
        解析单个榜单页面，提取所有图书数据

        使用lxml解析器（比html.parser更快，比html5lib更宽容），
        遍历榜单列表中的每个li元素，逐行解析为BookItem。

        参数:
            html: 页面完整HTML文本

        返回:
            本页解析到的BookItem列表，解析失败的行会被跳过
        """
        soup = BeautifulSoup(html, "lxml")
        items = []
        bang_list = soup.find("ul", class_="bang_list")
        if not bang_list:
            logger.warning("未找到 bang_list 容器")
            return items
        rows = bang_list.find_all("li")
        for row in rows:
            # 过滤非Tag节点（如NavigableString文本节点）
            if not isinstance(row, Tag):
                continue
            try:
                item = self._parse_row(row)
                if item and item.book_title:
                    items.append(item)
            except Exception as e:
                # 单行解析失败不影响整页，记录警告后继续
                logger.warning(f"解析行数据异常: {e}")
                continue
        logger.info(f"本页解析到 {len(items)} 条图书数据")
        return items

    def _parse_row(self, row: Tag) -> Optional[BookItem]:
        """
        解析单行图书数据，从li元素中提取各字段

        当当网榜单页面结构：
        - div.list_num: 排名数字
        - div.name > a: 书名和详情链接
        - div.publisher_info（第1个）: 作者信息
        - div.publisher_info（第2个）: 出版社信息
        - div.price: 当前价/原价/折扣
        - div.star: 评论数和好评度
        - div.pic > img: 封面图片

        参数:
            row: BeautifulSoup的li Tag对象

        返回:
            填充好字段的BookItem对象，解析失败返回None
        """
        item = BookItem()

        # === 排名 ===
        list_num = row.find("div", class_="list_num")
        if list_num:
            match = re.search(r"\d+", list_num.get_text(strip=True))
            if match:
                item.rank_position = int(match.group())

        # === 书名和详情链接 ===
        name_tag = row.find("div", class_="name")
        if name_tag:
            a_tag = name_tag.find("a")
            if a_tag:
                # 优先取title属性（更完整），其次取链接文本
                full_title = a_tag.get("title", "")
                item.book_title = full_title if full_title else a_tag.get_text(strip=True)
                item.detail_url = a_tag.get("href", "")
                # 当当网链接常省略"http:"前缀，需统一补全
                if item.detail_url and not item.detail_url.startswith("http"):
                    item.detail_url = "http:" + item.detail_url

        # === 作者和出版社 ===
        # 当当网页面有两个publisher_info div：第一个是作者，第二个是出版社
        publisher_infos = row.find_all("div", class_="publisher_info")
        if len(publisher_infos) >= 1:
            item.author = self._extract_author(publisher_infos[0])
        if len(publisher_infos) >= 2:
            item.publisher = self._extract_publisher(publisher_infos[1])

        # === 价格信息 ===
        price_tag = row.find("div", class_="price")
        if price_tag:
            # 当前售价
            price_n = price_tag.find("span", class_="price_n")
            if price_n:
                m = re.search(r"[\d.]+", price_n.get_text(strip=True))
                if m:
                    item.current_price = float(m.group())
            # 原价/定价
            price_r = price_tag.find("span", class_="price_r")
            if price_r:
                m = re.search(r"[\d.]+", price_r.get_text(strip=True))
                if m:
                    item.original_price = float(m.group())
            # 折扣率
            price_s = price_tag.find("span", class_="price_s")
            if price_s:
                m = re.search(r"[\d.]+", price_s.get_text(strip=True))
                if m:
                    item.discount = float(m.group())

        # === 评论数和好评度 ===
        star_tag = row.find("div", class_="star")
        if star_tag:
            # 评论数：从<a>标签文本中提取数字
            comment_a = star_tag.find("a")
            if comment_a:
                m = re.search(r"[\d,]+", comment_a.get_text(strip=True))
                if m:
                    item.comment_count = int(m.group().replace(",", ""))
            # 好评度：从内部<span>的CSS width百分比提取
            level_span = star_tag.find("span", class_="level")
            if level_span:
                inner = level_span.find("span")
                if inner:
                    style = inner.get("style", "")
                    m = re.search(r"width\s*:\s*([\d.]+)\s*%", style)
                    if m:
                        item.rating = float(m.group(1))

        # === 封面图片 ===
        pic_tag = row.find("div", class_="pic")
        if pic_tag:
            img = pic_tag.find("img")
            if img:
                # data-original用于懒加载场景，优先取src
                item.cover_image = img.get("src", "") or img.get("data-original", "")
                if item.cover_image and not item.cover_image.startswith("http"):
                    item.cover_image = "http:" + item.cover_image

        # === 折扣自动计算 ===
        # 如果页面未提供折扣，但有价格和原价，则自动计算
        if item.current_price and item.original_price and item.original_price > 0:
            if not item.discount:
                item.discount = round(item.current_price / item.original_price * 10, 1)

        return item

    @staticmethod
    def _extract_author(info_div: Tag) -> Optional[str]:
        """
        从作者信息div中提取创作者名称

        采用两步回退策略：
        1. 优先从<a>链接提取（当当网通常将作者名设为可点击链接）
        2. 若无链接，则从纯文本中用正则提取中英文姓名

        参数:
            info_div: 包含作者信息的div.publisher_info标签

        返回:
            创作者名称字符串（多位作者用中文逗号分隔），无则返回None
        """
        author_parts = []
        # 第一步：从链接提取（最可靠的方式）
        links = info_div.find_all("a")
        if links:
            for a in links:
                name = a.get_text(strip=True)
                if name and name not in author_parts:
                    author_parts.append(name)
        # 第二步：从纯文本提取（回退方案）
        if not author_parts:
            full_text = info_div.get_text(strip=True)
            # 按"/"、空格、全角空格分割多位作者
            segments = re.split(r"[/\s　]", full_text)
            for seg in segments:
                seg = seg.strip().strip("，,")
                if not seg:
                    continue
                # 匹配中文姓名（含间隔号·）和英文姓名
                name_match = re.search(r"[\u4e00-\u9fff·a-zA-Z\s]+", seg)
                if name_match:
                    cleaned = name_match.group().strip()
                    # 过滤占位符
                    if cleaned and cleaned not in ("—", "-", "无", "暂无"):
                        author_parts.append(cleaned)
        return "，".join(author_parts) if author_parts else None

    @staticmethod
    def _extract_publisher(info_div: Tag) -> Optional[str]:
        """
        从出版社信息div中提取出版社名称

        当当网页面中出版社div可能混入出版日期文本，
        需要先用正则移除日期后再提取出版社名。

        参数:
            info_div: 包含出版社信息的div.publisher_info标签

        返回:
            出版社名称字符串，无则返回None
        """
        # 优先从链接提取
        links = info_div.find_all("a")
        if links:
            for link in links:
                pub = link.get_text(strip=True)
                if pub and pub not in ("—", "-", "无", "暂无"):
                    return pub
        # 回退：从纯文本提取，需移除混入的出版日期
        text = info_div.get_text(strip=True)
        date_match = re.search(r"\d{4}[-\.]\d{1,2}[-\.]\d{1,2}", text)
        if date_match:
            text = text.replace(date_match.group(), "")
        text = text.strip().strip("，").strip(",")
        if text and text not in ("—", "-", "无", "暂无"):
            return text
        return None

    def fetch_detail_info(self, item: BookItem) -> None:
        """
        访问图书详情页，提取分类和出版时间等深层信息

        详情页包含列表页无法获取的重要字段：
        - 分类：从面包屑导航提取，如"图书 > 小说 > 当代小说"
        - 出版时间：从商品信息区提取，如"2024年3月"

        编码检测策略：
        当当网页面编码不统一（GBK/UTF-8），采用"锚点验证法"：
        依次尝试utf-8/gbk/gb2312编码，用书名前3个字作为锚点，
        如果解码后文本包含锚点，则认为编码正确。

        参数:
            item: BookItem对象，需已填充detail_url字段，方法会就地修改item
        """
        if not item.detail_url:
            return
        try:
            headers = {"User-Agent": generate_user_agent()}
            resp = requests.get(item.detail_url, headers=headers, timeout=10)
            # 编码检测：用书名前3字作为锚点验证编码是否正确
            for enc in ("utf-8", "gbk", "gb2312"):
                try:
                    resp.encoding = enc
                    if item.book_title and item.book_title[:3] in resp.text:
                        break
                except Exception:
                    continue
            else:
                # 所有编码都不匹配时，默认使用GBK（当当网最常见编码）
                resp.encoding = "gbk"
            soup = BeautifulSoup(resp.text, "lxml")

            # === 提取分类 ===
            # 从面包屑导航提取分类路径，通常格式为"图书 > 小说 > 当代小说"
            cat_path_elem = soup.find("li", id="detail-category-path")
            if cat_path_elem:
                cat_links = cat_path_elem.find_all("a")
                cat_names = [a.get_text(strip=True) for a in cat_links]
                if len(cat_names) >= 2:
                    # 取第二级分类（第一级通常是"图书"），如"小说"
                    main_cat = cat_names[1] if cat_names[0] == "图书" else cat_names[-2]
                    item.category = main_cat

            # === 提取出版时间（三级回退） ===
            # 第一级：从<span class="t1">标签提取（最精确）
            pub_time_span = soup.find("span", class_="t1", string=re.compile(r"出版时间"))
            if pub_time_span:
                pub_text = pub_time_span.next_sibling
                if pub_text:
                    m = re.search(r"[\d年月]+", str(pub_text))
                    if m:
                        item.publish_date = m.group().replace("年", "-").replace("月", "").rstrip("-")
                # 第二级：从父元素文本提取
                if not item.publish_date:
                    parent = pub_time_span.parent
                    if parent:
                        m = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月", parent.get_text())
                        if m:
                            item.publish_date = f"{m.group(1)}-{m.group(2).zfill(2)}"
            # 第三级：从detail_describe区域提取（兜底方案）
            if not item.publish_date:
                detail_describe = soup.find("div", id="detail_describe")
                if detail_describe:
                    m = re.search(r"出版时间[：:]\s*(\d{4})\s*年\s*(\d{1,2})\s*月", detail_describe.get_text())
                    if m:
                        item.publish_date = f"{m.group(1)}-{m.group(2).zfill(2)}"
                    else:
                        m = re.search(r"出版时间[：:]\s*(\d{4}[-\.]\d{1,2})", detail_describe.get_text())
                        if m:
                            item.publish_date = m.group(1).replace(".", "-")
        except Exception as e:
            # 详情页获取失败不影响主流程，仅记录debug日志
            logger.debug(f"获取详情页失败 {item.detail_url}: {e}")
