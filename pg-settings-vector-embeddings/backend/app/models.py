# SQLAlchemy ORM models representing your PostgreSQL tables.
# Includes tables like - SettingEmbedding, Insights

from sqlalchemy import Column, String, Text
from pgvector.sqlalchemy import Vector
from .database import Base

class Insights(Base):
    __tablename__ = 'insights'
    settings_name = Column(String, primary_key=True, index=True)
    ai_insights = Column(Text)

class InsightEmbeddings(Base):
    __tablename__ = 'insight_embeddings'
    settings_name = Column(Text, primary_key=True, index=True)
    embedding = Column(Vector(384))

class PgSettingsMetadataEmbeddings(Base):
    __tablename__ = 'pg_settings_metadata_embeddings'
    name = Column(Text, primary_key=True, index=True)
    embedding = Column(Vector(384))
    current_value = Column(Text)
    default_value = Column(Text)
    short_desc = Column(Text)
    context = Column(Text)
    vartype = Column(Text)
    min_val = Column(Text)
    max_val = Column(Text)

# class SettingEmbedding(Base):
#     __tablename__ = 'setting_embeddings'
#     settings_name = Column(String, primary_key=True)
#     embedding = Column(Vector(384))  # dimension = 384
