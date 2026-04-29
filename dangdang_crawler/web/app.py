"""
Flask Web应用模块：提供HTTP API和页面路由

本模块是前后端交互的核心，负责：
- 页面路由：渲染主页面，传递时间范围和字段配置
- 爬取控制API：启动/停止/暂停爬取任务，支持断点续爬
- 数据库API：初始化/保存/查询/删除批次数据
- 数据导出API：CSV格式导出
- 状态轮询API：供前端定时获取爬取进度和数据
"""

import csv
import io
import threading
from datetime import date

from flask import Flask, render_template, request, jsonify, Response

from dangdang_crawler.core.parser import BookItem
from dangdang_crawler.core.scheduler import TaskScheduler
from dangdang_crawler.core.spider import CrawlTask
from dangdang_crawler.database.connector import DatabaseConnector
from dangdang_crawler.database.models import BookRanking
from dangdang_crawler.utils.config import ConfigManager
from dangdang_crawler.utils.helpers import FIELD_NAMES, TIME_RANGE_MAP, DEFAULT_UNSELECTED_FIELDS, generate_batch_id
from dangdang_crawler.utils.logger import LoggerManager


logger = LoggerManager().get_logger("web")


def create_app(config: ConfigManager | None = None) -> Flask:

    app = Flask(__name__, template_folder="templates", static_folder="static")

    if config is None:
        config = ConfigManager()
    cfg = config
    db = DatabaseConnector()
    scheduler = TaskScheduler(cfg)
    all_items: list[BookItem] = []
    lock = threading.Lock()

    db_cfg = cfg.get_db_config()
    try:
        db.connect(**db_cfg)
        logger.info("数据库自动连接成功")
    except Exception:
        logger.warning("数据库自动连接失败")

    @app.route("/")
    def index():
        from datetime import date
        return render_template("index.html", time_ranges=TIME_RANGE_MAP, fields=FIELD_NAMES, default_unselected=DEFAULT_UNSELECTED_FIELDS, current_year=date.today().year)

    @app.route("/api/start", methods=["POST"])
    def start_crawl():
        data = request.json or {}
        ranking_type = data.get("ranking_type", "bestseller")
        time_range = data.get("time_range", "24hours")
        start_page = int(data.get("start_page", 1))
        end_page = int(data.get("end_page", 3))
        resume = data.get("resume", False)
        if start_page > end_page:
            return jsonify({"ok": False, "msg": "起始页不能大于结束页"})

        actual_start = start_page
        resume_info = ""
        if resume and db.is_connected:
            batch_id = generate_batch_id(ranking_type, time_range)
            try:
                max_rank = db.get_max_rank(batch_id)
                if max_rank > 0:
                    crawled_pages = (max_rank + 19) // 20
                    if crawled_pages >= end_page:
                        return jsonify({"ok": False, "msg": f"批次 {batch_id} 已有 {max_rank} 条数据（{crawled_pages} 页），无需续爬"})
                    actual_start = crawled_pages + 1
                    resume_info = f"（续爬：已有{max_rank}条/{crawled_pages}页，从第{actual_start}页继续）"
            except Exception:
                pass

        task = CrawlTask(ranking_type=ranking_type, time_range=time_range, start_page=actual_start, end_page=end_page)
        with lock:
            all_items.clear()
        def on_data(items):
            with lock:
                if len(items) > len(all_items):
                    all_items.clear()
                    all_items.extend(items)
                else:
                    for i, new_item in enumerate(items):
                        if i < len(all_items):
                            all_items[i] = new_item
                        else:
                            all_items.append(new_item)
        scheduler.set_callbacks(on_data=on_data)
        scheduler.start_task(task)
        msg = f"爬取任务已启动{resume_info}" if resume_info else "爬取任务已启动"
        return jsonify({"ok": True, "msg": msg, "actual_start": actual_start, "resumed": actual_start > start_page})

    @app.route("/api/stop", methods=["POST"])
    def stop_crawl():
        scheduler.stop_task()
        return jsonify({"ok": True, "msg": "已停止"})

    @app.route("/api/pause", methods=["POST"])
    def pause_crawl():
        if scheduler.is_paused:
            scheduler.resume_task()
            return jsonify({"ok": True, "msg": "已恢复", "paused": False})
        else:
            scheduler.pause_task()
            return jsonify({"ok": True, "msg": "已暂停", "paused": True})

    @app.route("/api/status", methods=["GET"])
    def get_status():
        items_snapshot = scheduler.get_all_items()
        return jsonify({
            "running": scheduler.is_running,
            "paused": scheduler.is_paused,
            "count": len(items_snapshot),
            "items": [_item_to_dict(item) for item in items_snapshot],
        })

    @app.route("/api/save_db", methods=["POST"])
    def save_to_db():
        data = request.json or {}
        ranking_type = data.get("ranking_type", "bestseller")
        time_range = data.get("time_range", "24hours")
        with lock:
            items_snapshot = list(all_items)
        if not items_snapshot:
            return jsonify({"ok": False, "msg": "没有数据可保存"})
        if not db.is_connected:
            try:
                db.connect(**cfg.get_db_config())
            except Exception as e:
                return jsonify({"ok": False, "msg": f"数据库连接失败: {e}"})
        try:
            saved = db.save_items(items_snapshot, ranking_type, time_range)
            batch_id = generate_batch_id(ranking_type, time_range)
            return jsonify({"ok": True, "msg": f"成功保存 {saved} 条数据 (批次: {batch_id})"})
        except Exception as e:
            return jsonify({"ok": False, "msg": f"保存失败: {e}"})

    @app.route("/api/init_db", methods=["POST"])
    def init_db():
        try:
            db_cfg = cfg.get_db_config()
            db.create_database(**db_cfg)
            db.connect(**db_cfg)
            db.init_tables()
            return jsonify({"ok": True, "msg": "数据库初始化成功"})
        except Exception as e:
            return jsonify({"ok": False, "msg": f"初始化失败: {e}"})

    @app.route("/api/db_status", methods=["GET"])
    def db_status():
        return jsonify({"connected": db.is_connected})

    @app.route("/api/batches", methods=["GET"])
    def get_batches():
        if not db.is_connected:
            return jsonify({"ok": False, "msg": "数据库未连接", "batches": []})
        try:
            batches = db.get_all_batches()
            return jsonify({"ok": True, "batches": batches})
        except Exception as e:
            return jsonify({"ok": False, "msg": str(e), "batches": []})

    @app.route("/api/batch_items", methods=["GET"])
    def get_batch_items():
        batch_id = request.args.get("batch_id", "")
        if not batch_id or not db.is_connected:
            return jsonify({"ok": False, "items": []})
        try:
            items = db.get_batch_items(batch_id)
            return jsonify({"ok": True, "items": items})
        except Exception as e:
            return jsonify({"ok": False, "items": []})

    @app.route("/api/delete_batch", methods=["POST"])
    def delete_batch():
        data = request.json or {}
        batch_id = data.get("batch_id", "")
        if not batch_id or not db.is_connected:
            return jsonify({"ok": False, "msg": "参数错误或数据库未连接"})
        session = db.get_session()
        try:
            count = session.query(BookRanking).filter(BookRanking.batch_id == batch_id).delete()
            session.commit()
            return jsonify({"ok": True, "msg": f"已删除批次 {batch_id}，共 {count} 条数据"})
        except Exception as e:
            session.rollback()
            return jsonify({"ok": False, "msg": f"删除失败: {e}"})
        finally:
            session.close()

    @app.route("/api/export_csv", methods=["POST"])
    def export_csv():
        data = request.json or {}
        fields = data.get("fields", list(FIELD_NAMES.keys()))
        ranking_type = data.get("ranking_type", "bestseller")
        time_range = data.get("time_range", "24hours")
        with lock:
            items_snapshot = list(all_items)
        if not items_snapshot:
            return jsonify({"ok": False, "msg": "没有数据可导出"})
        batch_id = generate_batch_id(ranking_type, time_range)
        filename = f"dangdang_{batch_id}.csv"
        output = io.StringIO()
        writer = csv.writer(output)
        headers = [FIELD_NAMES.get(f, f) for f in fields]
        writer.writerow(headers)
        for item in items_snapshot:
            row = [_get_field_value(item, f) for f in fields]
            writer.writerow(row)
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    @app.route("/api/config", methods=["GET"])
    def get_config():
        return jsonify({"database": cfg.get_db_config(), "spider": cfg.get_spider_config(), "server": cfg.get_server_config()})

    return app


def _item_to_dict(item: BookItem) -> dict:
    """将BookItem对象转为字典，用于JSON序列化"""
    return {
        "rank_position": item.rank_position,
        "book_title": item.book_title,
        "introduction": item.introduction or "",
        "author": item.author or "",
        "publisher": item.publisher or "",
        "publish_date": item.publish_date or "",
        "current_price": item.current_price,
        "original_price": item.original_price,
        "discount": item.discount,
        "comment_count": item.comment_count,
        "rating": item.rating,
        "category": item.category or "",
        "detail_url": item.detail_url or "",
        "cover_image": item.cover_image or "",
    }


def _get_field_value(item: BookItem, field: str) -> str:
    """获取BookItem指定字段的字符串值，用于CSV导出"""
    val = getattr(item, field, None)
    if val is None:
        return ""
    return str(val)
