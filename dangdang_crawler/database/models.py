"""
ORM模型模块：定义图书榜单数据表结构

使用SQLAlchemy的声明式映射定义数据表，包含：
- BookRanking: 图书榜单数据表，存储爬取的图书信息
- 唯一约束: (batch_id, rank_position) 确保同一批次同一排名不重复
- to_dict方法: 将ORM对象转为字典，便于JSON序列化
"""

from datetime import date, datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    Numeric,
    Enum,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class BookRanking(Base):
    __tablename__ = "book_rankings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(String(30), nullable=False, index=True, comment="批次ID")
    rank_date = Column(Date, nullable=False, comment="榜单日期")
    ranking_type = Column(
        Enum("bestseller", "newhot", name="ranking_type_enum"),
        nullable=False,
        comment="榜单类型",
    )
    time_range = Column(String(20), nullable=False, comment="时间范围")
    rank_position = Column(Integer, nullable=False, comment="排名位置")
    book_title = Column(String(255), nullable=False, comment="图书标题")
    introduction = Column(String(500), comment="介绍/推荐语")
    author = Column(String(100), comment="创作者")
    publisher = Column(String(100), comment="出版社")
    publish_date = Column(String(20), comment="出版时间")
    current_price = Column(Numeric(10, 2), nullable=False, comment="当前价格")
    original_price = Column(Numeric(10, 2), comment="原价")
    discount = Column(Numeric(4, 1), comment="折扣率")
    comment_count = Column(Integer, comment="评论数")
    rating = Column(Numeric(5, 1), comment="好评度(%)")
    category = Column(String(100), comment="分类")
    detail_url = Column(String(500), comment="详情页URL")
    cover_image = Column(String(500), comment="封面图片URL")
    crawl_time = Column(DateTime, default=datetime.now, comment="爬取时间")

    __table_args__ = (
        UniqueConstraint(
            "batch_id",
            "rank_position",
            name="uniq_batch_rank",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "batch_id": self.batch_id,
            "rank_date": self.rank_date.isoformat() if self.rank_date else None,
            "ranking_type": self.ranking_type,
            "time_range": self.time_range,
            "rank_position": self.rank_position,
            "book_title": self.book_title,
            "introduction": self.introduction,
            "author": self.author,
            "publisher": self.publisher,
            "publish_date": self.publish_date,
            "current_price": float(self.current_price) if self.current_price else None,
            "original_price": float(self.original_price) if self.original_price else None,
            "discount": float(self.discount) if self.discount else None,
            "comment_count": self.comment_count,
            "rating": float(self.rating) if self.rating else None,
            "category": self.category,
            "detail_url": self.detail_url,
            "cover_image": self.cover_image,
            "crawl_time": self.crawl_time.isoformat() if self.crawl_time else None,
        }
