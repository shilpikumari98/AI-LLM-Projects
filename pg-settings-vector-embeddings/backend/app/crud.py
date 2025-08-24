from sqlalchemy.orm import Session
from sqlalchemy import text
from . import models

def get_insight(db: Session, settings_name: str):
    return db.query(models.Insights).filter(models.Insights.settings_name == settings_name).first()

# def get_embedding(db: Session, settings_name: str):
#     return db.query(models.SettingEmbedding).filter(models.SettingEmbedding.settings_name == settings_name).first()

def get_all_settings(db: Session):
    query = text("""
    SELECT name, setting AS current_value, boot_val AS default_value, short_desc, context, vartype, min_val, max_val
    FROM pg_settings
    ORDER BY name;
    """)
    result = db.execute(query).fetchall()
    return [
        {
            "name": r.name,
            "current_value": r.current_value,
            "default_value": r.default_value,
            "short_desc": r.short_desc,
            "context": r.context,
            "vartype": r.vartype,
            "min_val": r.min_val,
            "max_val": r.max_val,
        } for r in result
    ]
