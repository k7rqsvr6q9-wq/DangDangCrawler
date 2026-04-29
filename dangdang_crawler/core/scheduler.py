"""
任务调度模块：管理爬取任务的生命周期，支持异步执行和暂停/恢复/停止

本模块在Spider之上封装了一层调度逻辑，提供：
- 异步执行：在守护线程中运行爬取任务，不阻塞Flask主线程
- 数据缓冲：线程安全地缓存爬取结果，供Web API实时查询
- 生命周期管理：统一暴露start/stop/pause/resume接口
"""

import threading
from datetime import datetime
from typing import Callable, Optional

from dangdang_crawler.core.spider import CrawlTask, DangDangSpider
from dangdang_crawler.core.parser import BookItem
from dangdang_crawler.utils.config import ConfigManager
from dangdang_crawler.utils.logger import LoggerManager


logger = LoggerManager().get_logger("scheduler")


class TaskScheduler:
    """任务调度器：封装爬虫的异步执行、暂停/恢复/停止控制"""

    def __init__(self, config: ConfigManager | None = None):
        """初始化调度器：创建爬虫实例和数据缓冲区"""
        self._config = config or ConfigManager()
        self._spider = DangDangSpider(self._config)
        self._thread: Optional[threading.Thread] = None  # 工作线程
        self._all_items: list[BookItem] = []              # 数据缓冲区
        self._lock = threading.Lock()                     # 线程安全锁

    def set_callbacks(
        self,
        on_progress: Callable | None = None,
        on_log: Callable | None = None,
        on_data: Callable | None = None,
        on_finished: Callable | None = None,
    ):
        """设置回调函数，转发给爬虫实例"""
        self._spider.set_callbacks(
            on_progress=on_progress,
            on_log=on_log,
            on_data=self._on_data_wrapper(on_data),
            on_finished=on_finished,
        )

    def _on_data_wrapper(self, callback: Callable | None):
        """包装数据回调：在接收数据时同时存入缓冲区"""
        def wrapper(items: list[BookItem]):
            with self._lock:
                if len(items) >= len(self._all_items):
                    self._all_items = list(items)
                else:
                    self._all_items.extend(items)
            if callback:
                callback(items)
        return wrapper

    def start_task(self, task: CrawlTask, blocking: bool = False):
        """
        启动爬取任务

        参数:
            task: 爬取任务配置
            blocking: 是否阻塞当前线程（默认异步执行）
        """
        # 清空数据缓冲区
        with self._lock:
            self._all_items = []

        if blocking:
            # 阻塞模式：直接在当前线程执行
            self._spider.crawl(task)
        else:
            # 异步模式：在守护线程中执行
            self._thread = threading.Thread(
                target=self._spider.crawl,
                args=(task,),
                daemon=True,
            )
            self._thread.start()

    def stop_task(self):
        """停止当前爬取任务"""
        self._spider.stop()

    def pause_task(self):
        """暂停当前爬取任务"""
        self._spider.pause()

    def resume_task(self):
        """恢复当前爬取任务"""
        self._spider.resume()

    @property
    def is_running(self) -> bool:
        """查询任务是否正在运行"""
        return self._spider.is_running

    @property
    def is_paused(self) -> bool:
        """查询任务是否已暂停"""
        return self._spider.is_paused

    def get_all_items(self) -> list[BookItem]:
        """获取当前已爬取的所有数据（线程安全副本）"""
        with self._lock:
            crawled = getattr(self._spider, "_crawled_items", None)
            if crawled:
                return list(crawled)
            return list(self._all_items)
