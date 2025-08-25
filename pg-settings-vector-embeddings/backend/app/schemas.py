# Pydantic models for request and response validation.
# Ensures data correctness and auto-generates API docs.

from pydantic import BaseModel
from typing import Optional, List

class Insight(BaseModel):
    settings_name: str
    ai_insights: str

    class Config:
        from_attributes = True

class InsightEmbedding(BaseModel):
    settings_name: str
    embedding: List[float]   # Vector(384) represented as a list of floats

    class Config:
        from_attributes = True


class PgSettingsMetadataEmbedding(BaseModel):
    name: str
    embedding: List[float]
    current_value: Optional[str] = None
    default_value: Optional[str] = None
    short_desc: Optional[str] = None
    context: Optional[str] = None
    vartype: Optional[str] = None
    min_val: Optional[str] = None
    max_val: Optional[str] = None

    class Config:
        from_attributes = True

# class SettingEmbedding(BaseModel):
#     settings_name: str
#     embedding: list[float]

#     class Config:
#         from_attributes = True
