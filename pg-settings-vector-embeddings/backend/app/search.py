import re
import spacy
from rapidfuzz import process, fuzz
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import text
from sentence_transformers import SentenceTransformer
from rank_bm25 import BM25Okapi
from .llm_api import ask_setting_via_llm
import numpy as np

from .database import SessionLocal
from . import crud

router = APIRouter()

nlp = spacy.load("en_core_web_sm")

embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

ASPECT_KEYWORDS = [
    "default_value", "current_value", "description", "purpose", "usage", "effect", "role",
    "recommendation", "example", "range", "type", "min_value", "max_value", "context",
    "security", "performance", "minimum", "maximum", "min", "max"
]

INTENT_KEYWORDS = {
    "definition": ["what is", "explain", "describe", "definition", "meaning"],
    "recommendation": ["should i", "recommend", "suggest", "advice"],
    "impact": ["effect", "impact", "influence", "result", "consequence"],
    "comparison": ["difference", "compare", "vs", "versus"],
    "security": ["secure", "security", "risk", "attack", "vulnerability"],
    "performance": ["performance", "speed", "slow", "fast"]
}

TEMPLATES = {
    "definition": "{setting}: {description}\n\nAI Insight: {ai_insight}",
    "recommendation": "Recommendation for {setting}: {ai_insight}",
    "impact": "Impact of {setting}: {impact_text}",
    "comparison": "Comparison:\n{comparisons}",
    "security": "Security considerations for {setting}: {ai_insight}",
    "performance": "Performance of {setting}: {ai_insight}",
    "default": (
        "{setting} details:\nCurrent Value: {current_value}\nDefault Value: {default_value}\n"
        "Type: {vartype}\nRange: {min_val} - {max_val}\nContext: {context}\n"
        "Description: {description}\n\nAI Insight: {ai_insight}"
    ),
}

class SearchRequest(BaseModel):
    query: str

class SearchResponse(BaseModel):
    answer: str

def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def normalize_text(text: str) -> str:
    """Normalize text by lowering case and removing underscores and spaces."""
    return text.lower().replace("_", "").replace(" ", "")

def fuzzy_match_setting(query, settings, threshold=70):
    """Find the best matching setting using fuzzy search."""
    result = process.extractOne(query, settings, scorer=fuzz.token_sort_ratio)
    if result and result[1] >= threshold:
        return result[0]
    return None

def extract_aspect_spacy(query: str) -> str | None:
    normalized_query = normalize_text(query)
    for aspect in ASPECT_KEYWORDS:
        if normalize_text(aspect) in normalized_query:
            return aspect
    return None

def extract_entities_spacy(query):
    doc = nlp(query)
    return [ent.text for ent in doc.ents]

def classify_intent(query):
    query_l = query.lower()
    for intent, keywords in INTENT_KEYWORDS.items():
        for kw in keywords:
            if kw in query_l:
                return intent
    return "default"

def bm25_hybrid_search(query, docs, setting_names):
    """Perform BM25 search on setting descriptions."""
    if not docs or not setting_names:
        return None
    
    # Filter out None/empty descriptions and keep corresponding setting names
    valid_docs = []
    valid_names = []
    for doc, name in zip(docs, setting_names):
        if doc and doc.strip():
            valid_docs.append(doc)
            valid_names.append(name)
    
    if not valid_docs:
        return None
    
    tokenized_docs = [d.split() for d in valid_docs]
    bm25 = BM25Okapi(tokenized_docs)
    scores = bm25.get_scores(query.split())
    
    if len(scores) > 0:
        top_index = np.argmax(scores)
        return valid_names[top_index]
    return None

@router.post("/search", response_model=SearchResponse)
def search(request: SearchRequest, db: Session = Depends(get_db)):
    query = request.query.strip()
    if not query:
        return SearchResponse(answer="Please enter a query.")
    
    # 1. Try LLM first
    llm_answer = ask_setting_via_llm(query)
    if llm_answer:
        return SearchResponse(answer=llm_answer)
    # If LLM fails, fallback to embeddings logic

    # Get all available settings
    try:
        all_settings = [row.name for row in db.execute(text("SELECT name FROM pg_settings")).fetchall()]
        print(f"Total settings available: {len(all_settings)}")
        # Check if our test setting exists
        if 'autovacuum_analyze_scale_factor' in all_settings:
            print("✓ autovacuum_analyze_scale_factor exists in pg_settings")
            # Also check if it has AI insights
            try:
                insight_check = db.execute(text("SELECT settings_name FROM insights WHERE settings_name = :name"), 
                                        {"name": 'autovacuum_analyze_scale_factor'}).first()
                if insight_check:
                    print("✓ autovacuum_analyze_scale_factor has AI insights")
                else:
                    print("✗ autovacuum_analyze_scale_factor has NO AI insights")
            except:
                print("? Could not check AI insights")
        else:
            print("✗ autovacuum_analyze_scale_factor NOT found in pg_settings")
    except Exception as e:
        print(f"Error retrieving settings list: {e}")
        return SearchResponse(answer="Error retrieving settings list from database.")

    mentioned_settings = set()

    # 1. Smart setting matching - prioritize exact/longer matches
    query_lower = query.lower()
    
    # First pass: exact matches and word boundary matches
    exact_matches = []
    partial_matches = []
    
    for setting in all_settings:
        setting_lower = setting.lower()
        
        # Check if setting appears as a complete word/token in query
        if setting_lower in query_lower:
            # Check if it's a word boundary match (not part of another word)
            import re
            pattern = r'\b' + re.escape(setting_lower) + r'\b'
            if re.search(pattern, query_lower):
                exact_matches.append(setting)
            else:
                partial_matches.append(setting)
        
        # Also check reverse (query word in setting name)
        elif query_lower in setting_lower:
            partial_matches.append(setting)
    
    # Prioritize exact matches, then longer partial matches
    if exact_matches:
        mentioned_settings.update(exact_matches)
    elif partial_matches:
        # Sort by length (longer settings first) and take the longest one
        longest_match = max(partial_matches, key=len)
        mentioned_settings.add(longest_match)
    
    print(f"Exact matches: {exact_matches}")
    print(f"Partial matches: {partial_matches}")
    print(f"Final mentioned_settings: {mentioned_settings}")

    # 2. spaCy NER + fuzzy match on entities (only if still no matches)
    if not mentioned_settings:
        entities = extract_entities_spacy(query)
        for ent in entities:
            fuzzy_ent = fuzzy_match_setting(ent, all_settings, threshold=50)
            if fuzzy_ent:
                mentioned_settings.add(fuzzy_ent)
                print(f"Entity fuzzy matched: {fuzzy_ent}")

    intent = classify_intent(query)
    aspect = extract_aspect_spacy(query)

    print(f"Query: {query}")
    print(f"Mentioned settings: {mentioned_settings}")
    print(f"Intent: {intent}")
    print(f"Aspect: {aspect}")
    
    # If no settings found through direct matching, try fuzzy matching
    if not mentioned_settings:
        print("No direct matches found, trying fuzzy matching...")
        fuzzy_candidate = fuzzy_match_setting(query, all_settings, threshold=50)
        if fuzzy_candidate:
            mentioned_settings.add(fuzzy_candidate)
            print(f"Fuzzy matched: {fuzzy_candidate}")
        
        # Also try fuzzy matching on individual words
        words = query.lower().split()
        for word in words:
            if len(word) > 3:  # Only try meaningful words
                fuzzy_ent = fuzzy_match_setting(word, all_settings, threshold=60)
                if fuzzy_ent:
                    mentioned_settings.add(fuzzy_ent)
                    print(f"Word '{word}' fuzzy matched: {fuzzy_ent}")

    # Handle multiple settings
    if len(mentioned_settings) > 1:
        if intent == "comparison":
            # Multi-setting comparison
            comparisons = []
            for s in mentioned_settings:
                try:
                    data = db.execute(text("""
                        SELECT name, setting AS current_value, boot_val AS default_value, short_desc, context, vartype, min_val, max_val
                        FROM pg_settings WHERE name = :name
                    """), {"name": s}).first()
                    if not data:
                        continue
                    ai_obj = crud.get_insight(db, s)
                    ai_text = ai_obj.ai_insights if ai_obj else "No insight available."
                    part = f"- {s}: Current={data.current_value}, Default={data.default_value}, Type={data.vartype}, Desc={data.short_desc}\nAI: {ai_text}"
                    comparisons.append(part)
                except Exception as e:
                    print(f"Error fetching comparison data for {s}: {e}")
                    continue
            if comparisons:
                answer = TEMPLATES['comparison'].format(comparisons='\n'.join(comparisons))
                return SearchResponse(answer=answer)
        else:
            # Multiple settings but not comparison intent - pick the most relevant one
            # Priority: longest name (most specific), then alphabetical
            best_setting = max(mentioned_settings, key=lambda x: (len(x), -ord(x[0])))
            mentioned_settings = {best_setting}
            print(f"Multiple settings found, selected most specific: {best_setting}")

    # Single setting detailed answer
    if len(mentioned_settings) == 1:
        setting = mentioned_settings.pop()
        print(f"Processing single setting: {setting}")
        
        try:
            setting_data = db.execute(text("""
                SELECT name, setting AS current_value, boot_val AS default_value, short_desc, context, vartype, min_val, max_val
                FROM pg_settings WHERE name = :name
            """), {"name": setting}).first()
            
            if not setting_data:
                print(f"No setting_data found for: {setting}")
                return SearchResponse(answer=f"No metadata found for setting '{setting}'.")
                
            ai_obj = crud.get_insight(db, setting)
            ai_text = ai_obj.ai_insights if ai_obj else "No AI insight available."
            
            print(f"Setting data found: {setting_data.name}")
            print(f"AI insight available: {bool(ai_obj)}")
            print(f"AI text preview: {ai_text[:100] if ai_text != 'No AI insight available.' else 'No insight'}")
            
        except Exception as e:
            print(f"Error retrieving setting data for {setting}: {e}")
            return SearchResponse(answer=f"Error retrieving setting data for '{setting}'.")

        # Handle specific aspects
        keys_map = {
            "default_value": "default_value",
            "current_value": "current_value", 
            "description": "short_desc",
            "purpose": "short_desc",
            "usage": "short_desc",
            "effect": "short_desc",
            "role": "context",
            "recommendation": None,
            "example": None,
            "type": "vartype",
            "min_value": "min_val",
            "max_value": "max_val",
            "context": "context",
            "security": None,
            "performance": None,
            "minimum": "min_val",
            "maximum": "max_val",
            "min": "min_val",
            "max": "max_val",
            "range": None
        }

        if aspect:
            if aspect == "range":
                min_val = setting_data.min_val or 'N/A'
                max_val = setting_data.max_val or 'N/A'
                answer = f"Range of values allowed for {setting}: {min_val} - {max_val}"
                return SearchResponse(answer=answer)
            key = keys_map.get(aspect)
            if key and getattr(setting_data, key, None):
                aspect_val = getattr(setting_data, key)
                answer = f"{setting} ({aspect}): {aspect_val}"
                return SearchResponse(answer=answer)
            elif aspect in ["recommendation", "security", "performance"] and ai_text and ai_text != "No AI insight available.":
                answer = TEMPLATES.get(aspect, TEMPLATES['default']).format(setting=setting, ai_insight=ai_text)
                return SearchResponse(answer=answer)
            else:
                return SearchResponse(answer=f"{setting} info: {ai_text[:400] if ai_text != 'No AI insight available.' else 'No detailed insight available for this aspect.'}")

        # Use appropriate template based on intent
        template_key = intent if intent in TEMPLATES else "default"
        answer = TEMPLATES[template_key].format(
            setting=setting_data.name,
            current_value=setting_data.current_value,
            default_value=setting_data.default_value,
            vartype=setting_data.vartype,
            min_val=setting_data.min_val or 'N/A',
            max_val=setting_data.max_val or 'N/A',
            context=setting_data.context or 'N/A',
            description=setting_data.short_desc or 'N/A',
            ai_insight=ai_text,
            impact_text=ai_text
        )
        return SearchResponse(answer=answer)

    # FALLBACK SEARCH: BM25 + Vector Similarity
    bm25_setting_name = None
    vector_setting_metadata = None
    vector_setting_insights = None

    # 1. BM25 search on pg_settings descriptions (FIXED: query correct table)
    try:
        settings_with_desc = db.execute(text("SELECT name, short_desc FROM pg_settings WHERE short_desc IS NOT NULL")).fetchall()
        if settings_with_desc:
            docs = [row.short_desc for row in settings_with_desc]
            setting_names = [row.name for row in settings_with_desc]
            bm25_setting_name = bm25_hybrid_search(query, docs, setting_names)
            print(f"BM25 found: {bm25_setting_name}")
    except Exception as e:
        print(f"BM25 search error: {e}")

    # 2. Vector similarity search on pg_settings_metadata_embeddings (FIXED: use correct column name)
    try:
        query_embedding = embedding_model.encode([query])[0].tolist()
        result = db.execute(text("""
            SELECT settings_name FROM pg_settings_metadata_embeddings
            ORDER BY embedding <-> :vec::vector
            LIMIT 1
        """), {"vec": query_embedding}).fetchone()
        vector_setting_metadata = result.settings_name if result else None
        print(f"Vector search (metadata) found: {vector_setting_metadata}")
    except Exception as e:
        print(f"Vector search (metadata) error: {e}")

    # 3. Vector similarity search on insight_embeddings for AI insight queries
    if any(keyword in query.lower() for keyword in ["recommend", "advice", "suggest", "insight", "should"]):
        try:
            result = db.execute(text("""
                SELECT settings_name FROM insight_embeddings
                ORDER BY embedding <-> :vec::vector
                LIMIT 1
            """), {"vec": query_embedding}).fetchone()
            vector_setting_insights = result.settings_name if result else None
            print(f"Vector search (insights) found: {vector_setting_insights}")
        except Exception as e:
            print(f"Vector search (insights) error: {e}")

    # Choose the best fallback result (prioritize insights for recommendation queries)
    fallback_setting = vector_setting_insights or bm25_setting_name or vector_setting_metadata

    if fallback_setting:
        try:
            setting_data = db.execute(text("""
                SELECT name, setting AS current_value, boot_val AS default_value, short_desc, context, vartype, min_val, max_val
                FROM pg_settings WHERE name = :name
            """), {"name": fallback_setting}).first()
            
            if not setting_data:
                return SearchResponse(answer=f"Setting '{fallback_setting}' not found in pg_settings.")
            
            ai_obj = crud.get_insight(db, fallback_setting)
            ai_text = ai_obj.ai_insights if ai_obj else "No AI insight available."
            
            answer = TEMPLATES['default'].format(
                setting=setting_data.name,
                current_value=setting_data.current_value,
                default_value=setting_data.default_value,
                vartype=setting_data.vartype,
                min_val=setting_data.min_val or 'N/A',
                max_val=setting_data.max_val or 'N/A',
                context=setting_data.context or 'N/A',
                description=setting_data.short_desc or 'N/A',
                ai_insight=ai_text,
                impact_text=ai_text
            )
            return SearchResponse(answer=answer)
        except Exception as e:
            print(f"Error retrieving fallback setting data: {e}")
            return SearchResponse(answer="Error retrieving fallback setting data.")

    return SearchResponse(answer="Sorry, no relevant information found for your query. Try being more specific or check the spelling of the setting name.")
