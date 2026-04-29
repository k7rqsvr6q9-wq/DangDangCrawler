"""
数据库连接模块：管理MySQL连接、表初始化和数据的CRUD操作

本模块封装了所有数据库操作，提供：
- 连接管理：自动重连、连接池、会话工厂
- 数据持久化：批量保存爬取结果（使用merge实现upsert）
- 数据查询：按批次/类型/时间范围查询
- 断点续爬支持：查询指定批次的最大排名位置
- 批次管理：列出/删除/查看批次数据
"""

from datetime import date, datetime
from urllib.parse import quote_plus

from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import Session, sessionmaker

from dangdang_crawler.core.parser import BookItem
from dangdang_crawler.database.models import Base, BookRanking
from dangdang_crawler.utils.helpers import generate_batch_id
from dangdang_crawler.utils.logger import LoggerManager


logger = LoggerManager().get_logger("database")


class DatabaseConnector:
    """数据库连接器"""

    def __init__(self):
        self._engine = None
        self._session_factory = None
        self._connected = False

    def connect(self, host="localhost", port=3306, username="root", password="", database="dangdang_data") -> bool:
        """连接到MySQL数据库"""
        try:
            url = f"mysql+pymysql://{username}:{quote_plus(password)}@{host}:{port}/{database}?charset=utf8mb4"
            self._engine = create_engine(url, echo=False, pool_pre_ping=True, pool_recycle=3600)
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            self._session_factory = sessionmaker(bind=self._engine)
            self._connected = True
            logger.info(f"数据库连接成功: {host}:{port}/{database}")
            return True
        except Exception as e:
            self._connected = False
            logger.error(f"数据库连接失败: {e}")
            raise

    def test_connection(self, host="localhost", port=3306, username="root", password="", database="dangdang_data") -> tuple[bool, str]:
        """测试数据库连接"""
        try:
            url = f"mysql+pymysql://{username}:{quote_plus(password)}@{host}:{port}/{database}?charset=utf8mb4"
            engine = create_engine(url, echo=False)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            engine.dispose()
            return True, "连接成功"
        except Exception as e:
            return False, f"连接失败: {str(e)}"

    def create_database(self, host="localhost", port=3306, username="root", password="", database="dangdang_data") -> bool:
        """创建数据库"""
        try:
            url = f"mysql+pymysql://{username}:{quote_plus(password)}@{host}:{port}/?charset=utf8mb4"
            engine = create_engine(url, echo=False)
            with engine.connect() as conn:
                conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
                conn.commit()
            engine.dispose()
            logger.info(f"数据库 {database} 创建成功")
            return True
        except Exception as e:
            logger.error(f"创建数据库失败: {e}")
            raise

    def init_tables(self):
        """初始化数据表结构"""
        if not self._engine:
            raise RuntimeError("数据库未连接")
        Base.metadata.create_all(self._engine)
        logger.info("数据表初始化完成")

    def get_session(self) -> Session:
        """获取数据库会话"""
        if not self._session_factory:
            raise RuntimeError("数据库未连接")
        return self._session_factory()

    def save_items(self, items: list[BookItem], ranking_type: str, time_range: str, rank_date: date | None = None) -> int:
        """保存爬取数据到数据库"""
        if not items:
            return 0
        if rank_date is None:
            rank_date = date.today()

        batch_id = generate_batch_id(ranking_type, time_range)
        session = self.get_session()
        saved = 0
        try:
            for item in items:
                record = BookRanking(
                    batch_id=batch_id,
                    rank_date=rank_date,
                    ranking_type=ranking_type,
                    time_range=time_range,
                    rank_position=item.rank_position,
                    book_title=item.book_title,
                    introduction=item.introduction,
                    author=item.author,
                    publisher=item.publisher,
                    publish_date=item.publish_date,
                    current_price=item.current_price if item.current_price else 0,
                    original_price=item.original_price,
                    discount=item.discount,
                    comment_count=item.comment_count,
                    rating=item.rating,
                    category=item.category,
                    detail_url=item.detail_url,
                    cover_image=item.cover_image,
                )
                session.merge(record)
                saved += 1
            session.commit()
            logger.info(f"保存 {saved} 条数据到数据库 (batch_id={batch_id})")
        except Exception as e:
            session.rollback()
            logger.error(f"保存数据失败: {e}")
            raise
        finally:
            session.close()
        return saved

    def query_items(self, ranking_type=None, time_range=None, batch_id=None, limit=100, offset=0) -> list[BookRanking]:
        """按条件查询数据"""
        session = self.get_session()
        try:
            q = session.query(BookRanking)
            if batch_id:
                q = q.filter(BookRanking.batch_id == batch_id)
            if ranking_type:
                q = q.filter(BookRanking.ranking_type == ranking_type)
            if time_range:
                q = q.filter(BookRanking.time_range == time_range)
            q = q.order_by(BookRanking.rank_position)
            return q.offset(offset).limit(limit).all()
        finally:
            session.close()

    def get_all_batches(self) -> list[dict]:
        """获取所有批次信息，用于数据库查看"""
        session = self.get_session()
        try:
            results = session.query(
                BookRanking.batch_id,
                BookRanking.ranking_type,
                BookRanking.time_range,
                BookRanking.rank_date,
            ).group_by(
                BookRanking.batch_id,
                BookRanking.ranking_type,
                BookRanking.time_range,
                BookRanking.rank_date,
            ).order_by(BookRanking.rank_date.desc()).all()
            return [
                {
                    "batch_id": r[0],
                    "ranking_type": r[1],
                    "time_range": r[2],
                    "rank_date": r[3].isoformat() if r[3] else None,
                }
                for r in results
            ]
        finally:
            session.close()

    def get_batch_items(self, batch_id: str, limit=500, offset=0) -> list[dict]:
        """获取指定批次的数据"""
        session = self.get_session()
        try:
            results = (
                session.query(BookRanking)
                .filter(BookRanking.batch_id == batch_id)
                .order_by(BookRanking.rank_position)
                .offset(offset)
                .limit(limit)
                .all()
            )
            return [r.to_dict() for r in results]
        finally:
            session.close()

    def get_max_rank(self, batch_id: str) -> int:
        """获取指定批次的最大排名位置，用于断点续爬"""
        session = self.get_session()
        try:
            result = session.query(func.max(BookRanking.rank_position)).filter(
                BookRanking.batch_id == batch_id
            ).scalar()
            return result or 0
        finally:
            session.close()

    def get_all_items_df(self) -> list[dict]:
        """获取所有数据"""
        session = self.get_session()
        try:
            return [r.to_dict() for r in session.query(BookRanking).all()]
        finally:
            session.close()

    @property
    def is_connected(self) -> bool:
        return self._connected

    def disconnect(self):
        if self._engine:
            self._engine.dispose()
            self._engine = None
            self._session_factory = None
            self._connected = False
            logger.info("数据库连接已关闭")
