"""
爬虫核心模块：负责HTTP请求、反爬策略、数据采集流程控制

本模块是整个爬虫系统的核心引擎，负责：
- HTTP会话管理：使用requests.Session保持连接复用，减少TCP握手开销
- 反爬策略：随机User-Agent轮换、请求间隔随机化、重试递增等待
- 数据采集流程：逐页爬取列表页 -> 批量获取详情页分类信息
- 任务控制：支持暂停/恢复/停止操作，通过状态标志实现
"""

import time
import traceback
from dataclasses import dataclass
from typing import Callable, Optional

import requests

from dangdang_crawler.core.cleaner import DataCleaner
from dangdang_crawler.core.parser import BookItem, DangDangParser
from dangdang_crawler.utils.config import ConfigManager
from dangdang_crawler.utils.helpers import build_dangdang_url, generate_user_agent, random_delay
from dangdang_crawler.utils.logger import LoggerManager


logger = LoggerManager().get_logger("spider")


@dataclass
class CrawlTask:
    """爬取任务数据类，包含一次爬取所需的全部参数"""
    ranking_type: str          # 榜单类型：bestseller 或 newhot
    time_range: str            # 时间范围：如 24hours、month-2026-1、year-2022
    start_page: int = 1        # 起始页码
    end_page: int = 1          # 结束页码
    fields: list[str] | None = None  # 需要采集的字段列表


class DangDangSpider:
    """当当网爬虫核心类，管理HTTP会话、请求调度和数据采集流程"""

    def __init__(self, config: ConfigManager | None = None):
        """初始化爬虫：加载配置、创建解析器和清洗器、初始化HTTP会话"""
        self._config = config or ConfigManager()
        self._parser = DangDangParser()       # HTML解析器
        self._cleaner = DataCleaner()         # 数据清洗器
        self._session = requests.Session()    # HTTP会话（保持连接复用）
        self._running = False                 # 运行状态标志
        self._paused = False                  # 暂停状态标志
        # 回调函数：用于向UI层通知进度、日志、数据、完成事件
        self._on_progress: Optional[Callable] = None
        self._on_log: Optional[Callable] = None
        self._on_data: Optional[Callable] = None
        self._on_finished: Optional[Callable] = None
        self._setup_session()

    def _setup_session(self):
        """配置HTTP会话：设置默认请求头和代理"""
        spider_cfg = self._config.get_spider_config()
        # 设置默认请求头，模拟浏览器访问
        self._session.headers.update({
            "User-Agent": generate_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        })
        # 如果配置了代理，设置会话代理
        if spider_cfg.get("use_proxy"):
            proxy_url = self._build_proxy_url(spider_cfg)
            if proxy_url:
                self._session.proxies = {"http": proxy_url, "https": proxy_url}

    def _build_proxy_url(self, cfg: dict) -> str | None:
        """根据配置构建代理URL，支持认证"""
        host = cfg.get("proxy_host", "")
        port = cfg.get("proxy_port", 0)
        if not host or not port:
            return None
        ptype = cfg.get("proxy_type", "http")
        username = cfg.get("proxy_username", "")
        password = cfg.get("proxy_password", "")
        # 如果有认证信息，构建带认证的URL
        if username and password:
            return f"{ptype}://{username}:{password}@{host}:{port}"
        return f"{ptype}://{host}:{port}"

    def set_callbacks(
        self,
        on_progress: Callable | None = None,
        on_log: Callable | None = None,
        on_data: Callable | None = None,
        on_finished: Callable | None = None,
    ):
        """设置回调函数，用于向UI层通知爬取状态"""
        self._on_progress = on_progress
        self._on_log = on_log
        self._on_data = on_data
        self._on_finished = on_finished

    def _emit_progress(self, current: int, total: int, message: str = ""):
        """发送进度通知"""
        if self._on_progress:
            try:
                self._on_progress(current, total, message)
            except Exception:
                pass

    def _emit_log(self, message: str):
        """发送日志通知"""
        logger.info(message)
        if self._on_log:
            try:
                self._on_log(message)
            except Exception:
                pass

    def _emit_data(self, items: list[BookItem]):
        """发送数据通知"""
        if self._on_data:
            try:
                self._on_data(items)
            except Exception:
                pass

    def _emit_finished(self, total_items: int):
        """发送完成通知"""
        if self._on_finished:
            try:
                self._on_finished(total_items)
            except Exception:
                pass

    def crawl(self, task: CrawlTask) -> list[BookItem]:
        """
        执行爬取任务的主方法

        逐页请求榜单页面，解析HTML提取数据，清洗后返回结果列表。
        支持暂停、恢复、停止操作。
        """
        self._running = True
        self._paused = False
        self._crawled_items: list[BookItem] = []
        all_items: list[BookItem] = []

        # 从配置中获取爬虫参数
        spider_cfg = self._config.get_spider_config()
        retry_count = spider_cfg.get("retry_count", 3)
        timeout = spider_cfg.get("timeout", 30)
        interval_min = spider_cfg.get("request_interval_min", 1.0)
        interval_max = spider_cfg.get("request_interval_max", 3.0)
        total_pages = task.end_page - task.start_page + 1

        self._emit_progress(0, total_pages, "开始爬取")

        for page in range(task.start_page, task.end_page + 1):
            if not self._running:
                self._emit_log("爬取已停止")
                break

            while self._paused:
                time.sleep(0.5)
                if not self._running:
                    break

            url = build_dangdang_url(task.ranking_type, task.time_range, page)
            self._emit_log(f"正在爬取第 {page} 页: {url}")
            self._emit_progress(page - task.start_page, total_pages + 1, f"正在爬取第 {page} 页")

            html = self._fetch_page(url, retry_count, timeout)
            if html:
                items = self._parser.parse_page(html)
                items = self._cleaner.clean_batch(items)
                for i, item in enumerate(items):
                    item.rank_position = (page - 1) * 20 + i + 1
                all_items.extend(items)
                self._emit_data(items)
                self._emit_log(f"第 {page} 页获取 {len(items)} 条数据")
            else:
                self._emit_log(f"第 {page} 页获取失败，跳过")

            if page < task.end_page:
                random_delay(interval_min, interval_max)

        if all_items:
            self._emit_log("正在获取详情页分类信息...")
            total_detail = len(all_items)
            for i, item in enumerate(all_items):
                if not self._running:
                    break
                self._parser.fetch_detail_info(item)
                if (i + 1) % 10 == 0:
                    self._emit_log(f"已获取 {i + 1}/{total_detail} 条详情")
                    self._emit_data(all_items)
                self._emit_progress(total_pages + (i + 1) / total_detail, total_pages + 1, f"获取详情 {i+1}/{total_detail}")
                time.sleep(0.3)
            self._emit_data(all_items)
            self._emit_log("详情页分类信息获取完成")

        self._running = False
        self._crawled_items = all_items
        self._emit_progress(total_pages + 1, total_pages + 1, "全部完成")
        self._emit_log(f"爬取完成，共获取 {len(all_items)} 条数据")
        self._emit_finished(len(all_items))
        return all_items

    def _fetch_page(self, url: str, retry_count: int = 3, timeout: int = 30) -> str | None:
        """
        请求单个页面，支持重试和编码自动检测

        当当网页面编码通常为GBK，部分页面为UTF-8，
        根据Content-Type头自动判断编码
        """
        for attempt in range(1, retry_count + 1):
            if not self._running:
                return None
            try:
                # 每次请求随机更换User-Agent
                self._session.headers["User-Agent"] = generate_user_agent()
                resp = self._session.get(url, timeout=timeout)
                resp.raise_for_status()
                # 默认使用GBK编码（当当网页面大多为GBK）
                resp.encoding = "gbk"
                # 如果Content-Type指示UTF-8，则切换编码
                content_type = resp.headers.get("Content-Type", "")
                if "utf" in content_type.lower():
                    resp.encoding = "utf-8"
                return resp.text
            except requests.RequestException as e:
                logger.warning(f"请求失败 (第{attempt}次): {e}")
                self._emit_log(f"请求失败 (第{attempt}/{retry_count}次): {e}")
                if attempt < retry_count:
                    time.sleep(2 * attempt)
        return None

    def stop(self):
        """停止爬取任务"""
        self._running = False
        self._paused = False
        self._emit_log("正在停止爬取...")

    def pause(self):
        """暂停爬取任务"""
        self._paused = True
        self._emit_log("爬取已暂停")

    def resume(self):
        """恢复爬取任务"""
        self._paused = False
        self._emit_log("爬取已恢复")

    @property
    def is_running(self) -> bool:
        """查询爬虫是否正在运行"""
        return self._running

    @property
    def is_paused(self) -> bool:
        """查询爬虫是否已暂停"""
        return self._paused
