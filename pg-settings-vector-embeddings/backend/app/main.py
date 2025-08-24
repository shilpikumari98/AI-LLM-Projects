import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import SessionLocal, engine
from . import models, schemas, crud, recommendation
from .search import router as search_router

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../frontend"))
app.mount("/static", StaticFiles(directory=frontend_path, html=True), name="static")

@app.get("/", response_class=FileResponse)
def serve_index():
    return FileResponse(os.path.join(frontend_path, "index.html"))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/settings")
def read_settings(db: Session = Depends(get_db)):
    return crud.get_all_settings(db)

@app.get("/insight/{settings_name}", response_model=schemas.Insight)
def read_insight(settings_name: str, db: Session = Depends(get_db)):
    insight = crud.get_insight(db, settings_name)
    if insight is None:
        raise HTTPException(status_code=404, detail="Insight not found")
    return insight

@app.get("/recommendations/{settings_name}")
def get_recommendations(settings_name: str, db: Session = Depends(get_db)):
    similar_settings = recommendation.find_similar_settings(db, settings_name)
    insights = []
    for s_name in similar_settings:
        insight = crud.get_insight(db, s_name)
        if insight:
            insights.append({"setting": s_name, "ai_insights": insight.ai_insights})
    if not insights:
        raise HTTPException(status_code=404, detail="No recommendations found")
    return insights

app.include_router(search_router)
