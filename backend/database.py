import datetime
import os

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(os.path.dirname(BASE_DIR), "ad_intelligence.db")
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Advertiser(Base):
    __tablename__ = "advertisers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    platform = Column(String)
    external_id = Column(String, unique=True)


class Ad(Base):
    __tablename__ = "ads"

    id = Column(Integer, primary_key=True, index=True)
    advertiser_id = Column(Integer, ForeignKey("advertisers.id"))
    external_id = Column(String, unique=True)
    platform = Column(String, index=True)
    advertiser_name = Column(String, index=True)
    brand_name = Column(String, index=True)
    page_name = Column(String, index=True)
    content = Column(Text)
    headline = Column(String)
    content_snippet = Column(Text, nullable=True)
    status = Column(String, nullable=True)
    category = Column(String, nullable=True)
    objective = Column(String, nullable=True)
    ad_format = Column(String, nullable=True)
    platforms = Column(String, nullable=True)
    start_date = Column(DateTime)
    end_date = Column(DateTime, nullable=True)
    first_shown_date = Column(DateTime, nullable=True)
    last_shown_date = Column(DateTime, nullable=True)
    rank = Column(String, nullable=True)
    display_rank = Column(String, nullable=True)
    ctr_rank = Column(String, nullable=True)
    impression_count = Column(String, nullable=True)
    spend = Column(String, nullable=True)
    likes = Column(String, nullable=True)
    budget_level = Column(String, nullable=True)
    region = Column(String, nullable=True)
    advertiser_location = Column(String, nullable=True)
    creative_url = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    landing_page = Column(String, nullable=True)
    landing_domain = Column(String, nullable=True)
    call_to_action = Column(String, nullable=True)
    variant_count = Column(String, nullable=True)
    raw_payload = Column(Text, nullable=True)
    query = Column(String, nullable=True)
    last_seen = Column(DateTime, default=datetime.datetime.utcnow)
    first_seen = Column(DateTime, default=datetime.datetime.utcnow)


AD_TABLE_MIGRATIONS = {
    "advertiser_name": "VARCHAR",
    "brand_name": "VARCHAR",
    "page_name": "VARCHAR",
    "content_snippet": "TEXT",
    "status": "VARCHAR",
    "category": "VARCHAR",
    "objective": "VARCHAR",
    "ad_format": "VARCHAR",
    "platforms": "VARCHAR",
    "first_shown_date": "DATETIME",
    "last_shown_date": "DATETIME",
    "rank": "VARCHAR",
    "display_rank": "VARCHAR",
    "ctr_rank": "VARCHAR",
    "impression_count": "VARCHAR",
    "spend": "VARCHAR",
    "likes": "VARCHAR",
    "budget_level": "VARCHAR",
    "region": "VARCHAR",
    "advertiser_location": "VARCHAR",
    "image_url": "VARCHAR",
    "landing_page": "VARCHAR",
    "landing_domain": "VARCHAR",
    "call_to_action": "VARCHAR",
    "variant_count": "VARCHAR",
    "raw_payload": "TEXT",
    "query": "VARCHAR",
}


def _ensure_ad_columns() -> None:
    inspector = inspect(engine)
    if "ads" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("ads")}
    with engine.begin() as connection:
        for column_name, column_type in AD_TABLE_MIGRATIONS.items():
            if column_name in existing_columns:
                continue
            connection.execute(text(f"ALTER TABLE ads ADD COLUMN {column_name} {column_type}"))


def init_db():
    Base.metadata.create_all(bind=engine)
    _ensure_ad_columns()
