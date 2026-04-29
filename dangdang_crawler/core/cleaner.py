"""
数据清洗模块：对解析后的图书数据进行标准化和去噪处理

核心功能是将当当网原始书名中的营销文字、副标题、版本信息等分离为"书名"和"介绍"两部分。
例如："见春天（新增番外《见答案》！总收藏量...)" -> 书名="见春天"，介绍="（新增番外...）"

书名分隔策略（从左到右依次执行）：
1. 册数/年份前缀剥离：如"全5册 快乐读书吧" -> 书名="快乐读书吧"
2. 丛书前缀反转：如"经典译林：xxx" -> 书名="xxx"
3. 冒号截断：如"五味太郎：小金鱼逃走了" -> 书名="小金鱼逃走了"
4. 括号截断：如"见春天（新增番外...）" -> 书名="见春天"
5. 空格截断：如"三体全集 电子版 全集无删减" -> 书名="三体全集"
6. 【】标记截断：如"书名【营销词】" -> 书名="书名"
7. 《》书名号处理：提取书名号内容
8. 版本后缀移除：如"正面管教修订版" -> 书名="正面管教"
9. 尾部清洗：去除省略号和无意义标点
"""

import re

from dangdang_crawler.core.parser import BookItem
from dangdang_crawler.utils.logger import LoggerManager


logger = LoggerManager().get_logger("cleaner")


class DataCleaner:
    """
    数据清洗器：对爬取的原始数据进行标准化处理

    主要职责：
    - 书名与介绍的分隔（核心功能，多策略从左到右扫描）
    - 创作者/出版社名称清洗（去除前缀标签和占位符）
    - 价格/折扣/评分的合理性校验
    - URL有效性检查
    """

    # 营销/描述性关键词，用于判断括号或冒号后的内容是否为介绍而非书名一部分
    _MARKETING_WORDS = (
        "总收藏量", "收藏量", "总点击", "点击量", "总销量", "销量",
        "豆瓣高分", "豆瓣评分", "豆瓣必读", "豆瓣推荐",
        "当当自营", "当当独家", "正版", "原著", "足本", "全译",
        "无删减", "完整版", "印签版", "签名版", "专享", "附赠",
        "赠品", "包邮", "现货", "限量", "推荐", "必读", "必读书",
        "老师推荐", "名家", "译者", "翻译",
        "电子版", "纸质版", "精装版", "平装版", "典藏版", "珍藏版",
        "特装版", "升级版", "修订版", "新版", "纪念版", "礼盒版",
        "套装", "全册", "全两册", "共四册",
        "课外阅读", "阅读书", "阅读书目", "快乐读书吧", "课程化",
        "小学生", "初中生", "高中生", "人教版", "部编版",
    )

    # 版本后缀正则模式，用于从书名末尾移除版本信息
    _EDITION_SUFFIXES = (
        r"第[一二三四五六七八九十\d]+版",
        r"[一二三四五六七八九十\d]+版$",
        r"\d+周年",
        r"纪念版$", r"修订版$", r"增订版$",
        r"典藏版$", r"珍藏版$", r"精装版$", r"平装版$",
        r"特装版$", r"升级版$", r"新版$",
    )

    # 册数/年份前缀正则，匹配书名开头的册数或年份标记
    _VOLUME_PREFIX_PATTERN = re.compile(
        r"^(全\d+册|共\d+册|\d+册套装|\d+本套装|全\d+本|"
        r"\d{4}年?新|最新版|最新修订|最新增订)"
    )

    # 丛书/系列前缀模式，当冒号前是这些前缀时，应取冒号后的内容作为书名
    _SERIES_PREFIX_PATTERNS = (
        r"名家名作阅读课程化书系",
        r"经典译林",
        r"名著名译",
        r"世界文学名著",
        r"中国古典文学",
        r"新课标",
        r"语文阅读丛书",
        r"名著阅读课程化丛书",
        r"果麦经典",
        r"读客经典",
        r"译林名著",
        r"开心作文",
        r"小书虫",
        r"大语文",
    )

    # 副标题模式，当冒号后匹配这些模式时，冒号是书名的一部分（应保留）
    _SUBTITLE_PATTERNS = (
        r"^从入门到实践",
        r"^从入门到精通",
        r"^从零开始",
        r"^实战指南",
        r"^入门经典",
        r"^权威指南",
        r"^核心技术",
        r"^深度学习",
        r"^基础教程",
    )

    def clean(self, item: BookItem) -> BookItem:
        """
        清洗单条图书数据，对各字段进行标准化处理

        参数:
            item: 待清洗的BookItem对象

        返回:
            清洗后的BookItem对象（就地修改并返回）
        """
        item.book_title, item.introduction = self._split_title(item.book_title)
        item.author = self._clean_author(item.author)
        item.publisher = self._clean_publisher(item.publisher)
        item.current_price = self._clean_price(item.current_price)
        item.original_price = self._clean_price(item.original_price)
        item.discount = self._clean_discount(item.discount)
        item.comment_count = self._clean_comment_count(item.comment_count)
        item.rating = self._clean_rating(item.rating)
        item.detail_url = self._clean_url(item.detail_url)
        item.cover_image = self._clean_url(item.cover_image)
        return item

    def clean_batch(self, items: list[BookItem]) -> list[BookItem]:
        """
        批量清洗数据，跳过清洗失败的条目

        参数:
            items: 待清洗的BookItem列表

        返回:
            清洗后的BookItem列表（可能比输入少，空书名的条目会被过滤）
        """
        cleaned = []
        for item in items:
            try:
                cleaned_item = self.clean(item)
                if cleaned_item.book_title:
                    cleaned.append(cleaned_item)
            except Exception as e:
                logger.warning(f"清洗数据异常，跳过: {e}")
        logger.info(f"数据清洗完成: 输入 {len(items)} 条, 输出 {len(cleaned)} 条")
        return cleaned

    @classmethod
    def _split_title(cls, title: str) -> tuple[str, str | None]:
        """
        将原始书名分隔为"主标题"和"介绍"两部分

        采用从左到右的多策略扫描方式，依次尝试各种分隔规则。
        一旦某个策略成功分离出介绍内容，后续策略仍可继续优化结果。

        参数:
            title: 原始书名字符串

        返回:
            (主标题, 介绍) 元组，介绍为None表示无介绍内容
        """
        if not title:
            return "", None

        raw = title.strip()
        introduction = None

        # Step 0: 册数/年份前缀剥离
        # 如"全5册 快乐读书吧" -> 书名="快乐读书吧", 介绍="全5册"
        m = cls._VOLUME_PREFIX_PATTERN.match(raw)
        if m:
            rest = raw[m.end():].strip()
            if rest and len(rest) > 1:
                introduction = m.group(0)
                raw = rest

        # Step 1: 丛书前缀反转
        # 如"经典译林：老人与海" -> 书名="老人与海", 介绍="经典译林"
        # 必须在冒号截断之前执行，否则冒号策略会把"经典译林"当书名
        for sp in cls._SERIES_PREFIX_PATTERNS:
            m = re.match(sp + r"[：: ]", raw)
            if m:
                rest = raw[m.end():].strip()
                if rest and len(rest) > 1:
                    prefix = raw[:m.end() - 1].strip()
                    introduction = prefix if not introduction else introduction + " " + prefix
                    raw = rest
                break

        # Step 2: 冒号截断
        # 从左到右扫描冒号，判断冒号是书名的一部分还是分隔符
        # 必须在括号策略之前，以便先处理"Python编程：从入门到实践 (第2版)"的冒号
        m = re.search(r"[：:]", raw)
        if m and m.start() > 1:
            colon_pos = m.start()
            before = raw[:colon_pos].strip()
            after = raw[colon_pos + 1:].strip()
            if not cls._is_colon_integral(raw, colon_pos):
                if len(before) > 1:
                    # 短中文名（3-4字）通常是作者名，取冒号后为书名
                    if 3 <= len(before) <= 4 and re.match(r"^[\u4e00-\u9fff]+$", before):
                        introduction = before if not introduction else introduction + " " + before
                        raw = after
                    else:
                        truncated = after
                        introduction = truncated if not introduction else introduction + " " + truncated
                        raw = before

        # Step 3: 括号截断
        # 从左到右扫描中文/英文左括号，括号后的内容视为附加信息
        m = re.search(r"[ \u3000]*[（(]", raw)
        if m and m.start() > 1:
            bracket_pos = m.start()
            before = raw[:bracket_pos].strip()
            after = raw[bracket_pos:].strip()
            if not cls._is_bracket_integral(raw, bracket_pos):
                if len(before) > 1:
                    introduction = after if not introduction else introduction + " " + after
                    raw = before

        # Step 3b: 清理括号截断后可能残留的前导空格
        raw = raw.strip()

        # Step 4: 空格截断
        # 从左到右扫描，第一个空格后的内容一律识别为介绍
        # 如"三体全集 电子版 全集无删减" -> 书名="三体全集"
        m = re.search(r"[ \u3000]", raw)
        if m and m.start() >= 1:
            space_pos = m.start()
            before = raw[:space_pos].strip()
            after = raw[space_pos + 1:].strip()
            if len(before) >= 1 and after:
                introduction = after if not introduction else introduction + " " + after
                raw = before

        # Step 5: 【】标记截断
        # 如"书名【当当自营】" -> 书名="书名"
        m = re.search(r"【", raw)
        if m and m.start() > 1:
            before = raw[:m.start()].strip()
            if len(before) > 1:
                rest = raw[m.start():]
                introduction = rest if not introduction else introduction + " " + rest
                raw = before

        # Step 6: 《》书名号处理
        # 提取书名号内的内容作为书名，书名号外的作为介绍
        m = re.search(r"《([^》]+)》", raw)
        if m:
            before = raw[:m.start()].strip()
            content = m.group(1).strip()
            after = raw[m.end():].strip()
            if before and len(before) > 1:
                parts = []
                if content:
                    parts.append(content)
                if after:
                    parts.append(after)
                if parts:
                    introduction = " ".join(parts) if not introduction else introduction + " " + " ".join(parts)
                raw = before
            elif content and len(content) > 1:
                intro_parts = []
                if after:
                    intro_parts.append(after)
                if intro_parts:
                    introduction = " ".join(intro_parts) if not introduction else introduction + " " + " ".join(intro_parts)
                raw = "《" + content + "》"

        # Step 7: 版本后缀移除
        # 如"正面管教修订版" -> 书名="正面管教", 介绍="修订版"
        for pat in cls._EDITION_SUFFIXES:
            m = re.search(pat, raw)
            if m and m.start() > 1:
                before = raw[:m.start()].strip()
                suffix = raw[m.start():].strip()
                if len(before) > 1:
                    introduction = suffix if not introduction else introduction + " " + suffix
                    raw = before
                break

        # Step 8: 尾部清洗
        # 去除末尾的省略号和无意义标点符号
        raw = raw.strip()
        raw = re.sub(r"[.。…]+\s*$", "", raw)
        raw = re.sub(r"[！!？?，,、：:；;~～—]+$", "", raw)
        raw = raw.strip()

        return raw, introduction

    @classmethod
    def _is_bracket_integral(cls, title: str, bracket_pos: int) -> bool:
        """
        判断括号内容是否为书名的不可分割部分

        保留括号的情况：版本信息如"(第5版)"
        截断括号的情况：营销文字如"(新增番外...)"、"(当当自营)"

        参数:
            title: 完整书名
            bracket_pos: 左括号在书名中的位置

        返回:
            True表示括号是书名一部分（应保留），False表示应截断
        """
        after = title[bracket_pos:]
        m = re.match(r"[（(]\s*([^）)]+)\s*[）)]", after)
        if not m:
            m = re.match(r"[（(]\s*(.+)$", after)
        if not m:
            return False

        content = m.group(1).strip()

        # 版本信息如"(第5版)"是书名不可分割的一部分
        if re.match(r"第[一二三四五六七八九十\d]+版", content):
            return True
        if re.match(r"第\d+版", content):
            return True

        # 包含营销关键词，不是书名的一部分
        for kw in cls._MARKETING_WORDS:
            if kw in content:
                return False

        # 内容过长，通常是营销描述
        if len(content) > 15:
            return False

        # 以营销性动词开头，不是书名的一部分
        if re.match(r"^(新增|新增番外|附|赠|送|含|全|共|当当|豆瓣|畅销|热销)", content):
            return False

        # 默认情况下截断括号内容（用户偏好简洁书名）
        return False

    @classmethod
    def _is_colon_integral(cls, title: str, colon_pos: int) -> bool:
        """
        判断冒号是否为书名的不可分割部分

        保留冒号的情况：副标题模式如"原则：生活和工作"
        截断冒号的情况：作者名如"五味太郎："、营销语如"活着：余华代表作"

        参数:
            title: 完整书名
            colon_pos: 冒号在书名中的位置

        返回:
            True表示冒号是书名一部分（应保留），False表示应截断
        """
        before = title[:colon_pos].strip()
        after = title[colon_pos + 1:].strip()

        # 丛书前缀后的冒号不是书名的一部分
        for sp in cls._SERIES_PREFIX_PATTERNS:
            if re.search(sp, before):
                return False

        # 3-4字纯中文名通常是作者名，冒号不是书名的一部分
        if 3 <= len(before) <= 4 and re.match(r"^[\u4e00-\u9fff]+$", before):
            return False

        # 冒号后是营销性内容，不是书名的一部分
        if cls._is_descriptive(after):
            return False

        # 冒号后匹配副标题模式，冒号是书名的一部分
        for sp in cls._SUBTITLE_PATTERNS:
            if re.match(sp, after):
                return True

        # 冒号后内容较短且不含营销词，视为副标题（保留冒号）
        if len(after) <= 10 and not cls._is_descriptive(after):
            has_marketing = any(kw in after for kw in cls._MARKETING_WORDS)
            if not has_marketing:
                return True

        # 默认保留冒号（保守策略，避免误截断副标题）
        return True

    @classmethod
    def _is_descriptive(cls, text: str) -> bool:
        """
        判断文本是否为营销/描述性内容而非副标题

        参数:
            text: 待判断的文本

        返回:
            True表示是营销描述性文字，False表示可能是副标题
        """
        for kw in cls._MARKETING_WORDS:
            if kw in text:
                return True
        if re.match(r"^(代表作|力作|经典|畅销|热销|热门|爆款|必看|高分|易读|通俗|全新|权威|精选|完整|足本|无删)", text):
            return True
        if re.search(r"(收藏|销量|点击|推荐|评分|豆瓣|译本|版本|解读|导读|注释|注释版)", text):
            return True
        return False

    @staticmethod
    def _clean_author(author: str | None) -> str | None:
        """
        清洗创作者名称：去除前缀标签、多余空格和占位符

        参数:
            author: 原始创作者字符串

        返回:
            清洗后的创作者名称，无效则返回None
        """
        if not author:
            return None
        author = author.strip()
        author = re.sub(r"^(作者|创作者)[：:]\s*", "", author)
        author = re.sub(r"\s+", " ", author)
        if not author or author in ("—", "-", "无", "暂无"):
            return None
        return author

    @staticmethod
    def _clean_publisher(publisher: str | None) -> str | None:
        """
        清洗出版社名称：去除前缀标签和占位符

        参数:
            publisher: 原始出版社字符串

        返回:
            清洗后的出版社名称，无效则返回None
        """
        if not publisher:
            return None
        publisher = publisher.strip()
        publisher = re.sub(r"^出版社[：:]\s*", "", publisher)
        if not publisher or publisher in ("—", "-", "无", "暂无"):
            return None
        return publisher

    @staticmethod
    def _clean_price(price: float | None) -> float | None:
        """清洗价格：负数视为无效，保留两位小数"""
        if price is None:
            return None
        if price < 0:
            return None
        return round(price, 2)

    @staticmethod
    def _clean_discount(discount: float | None) -> float | None:
        """清洗折扣：范围(0, 10]之外视为无效，保留一位小数"""
        if discount is None:
            return None
        if discount <= 0 or discount > 10:
            return None
        return round(discount, 1)

    @staticmethod
    def _clean_comment_count(count: int | None) -> int | None:
        """清洗评论数：负数视为无效"""
        if count is None:
            return None
        if count < 0:
            return None
        return count

    @staticmethod
    def _clean_rating(rating: float | None) -> float | None:
        """清洗好评度：范围[0, 100]之外视为无效，保留一位小数"""
        if rating is None:
            return None
        if rating < 0 or rating > 100:
            return None
        return round(rating, 1)

    @staticmethod
    def _clean_url(url: str | None) -> str | None:
        """清洗URL：空值、占位符和无效链接返回None"""
        if not url:
            return None
        url = url.strip()
        if not url or url in ("#", "javascript:void(0)"):
            return None
        return url

    @classmethod
    def detect_unsplit_titles(cls, titles: list[str]) -> list[tuple[int, str, str]]:
        """
        检测可能未正确分隔的书名，用于数据质量诊断

        扫描所有已分隔的书名，如果分隔后仍包含括号、空格、冒号等标志，
        则标记为可能未正确分隔。

        参数:
            titles: 原始书名列表

        返回:
            问题列表，每项为 (索引, 原始书名, 标志类型) 元组
        """
        issues = []
        for i, raw in enumerate(titles):
            title, intro = cls._split_title(raw)
            if intro is not None:
                continue
            if len(raw) <= 6:
                continue
            markers = []
            if re.search(r"[（(]", raw):
                markers.append("括号")
            if re.search(r"[【]", raw):
                markers.append("【】")
            if re.search(r"[《》]", raw):
                markers.append("《》")
            if re.search(r"[：:]", raw):
                markers.append("冒号")
            if re.search(r"[ \u3000]", raw):
                markers.append("空格")
            if markers:
                issues.append((i, raw, "/".join(markers)))
        return issues
