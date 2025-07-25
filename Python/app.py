from fastapi import FastAPI, HTTPException, Depends
from typing import Optional, List, Generator
import sqlalchemy as sa
from sqlmodel import Field, SQLModel, create_engine, Session, select
import os
from dotenv import load_dotenv 
from datetime import datetime, timezone
import re
from fastapi.middleware.cors import CORSMiddleware
from models import HelpdeskKBItem, HelpdeskKBItemCreate, HelpdeskKBItemRead, HelpdeskKBCategory, HelpdeskKBCategoryCreate, HelpdeskKBCategoryRead
from search import find_similar_items_embeddings

load_dotenv() 

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "15432")
DB_NAME = os.environ.get("DB_NAME", "test")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "password") 

DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}@"
    f"{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(DATABASE_URL)

def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session

app = FastAPI()

origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://127.0.0.1",
    "null"  
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)

@app.post("/items/", response_model=HelpdeskKBItemRead)
async def create_item(*, item: HelpdeskKBItemCreate, session: Session = Depends(get_session)):
    # Convert the Pydantic input model to the SQLModel table instance
    db_item = HelpdeskKBItem.model_validate(item)
    try:
        session.add(db_item)
        session.commit()
        session.refresh(db_item) # Refresh to get the auto-generated ID from the database
        return db_item
    except Exception as e:
        session.rollback()
        # Log the full exception for debugging, but return a generic message to client
        print(f"Error creating item: {e}")
        raise HTTPException(status_code=500, detail="Failed to create item due to a database error.")

@app.get("/items/{item_id}", response_model=HelpdeskKBItemRead)
async def read_item(*, item_id: int, session: Session = Depends(get_session)):
    # Ensure all fields required by HelpdeskKBItemRead are selected
    query = sa.text(
        "SELECT id, title, question, answer, votes, recommendations, last_updated, enabled, category_id, team_id, \"order\" "
        "FROM helpdesk_kbitem WHERE id = :item_id"
    )
    # Use .first() to get a single Row object
    result = session.exec(query.params(item_id=item_id)).first()

    if not result:
        raise HTTPException(status_code=404, detail="Item not found")

    return HelpdeskKBItemRead.model_validate(result._asdict())

@app.get("/items/", response_model=List[HelpdeskKBItemRead])
async def read_all_items(*, session: Session = Depends(get_session)):
    # Ensure all fields required by HelpdeskKBItemRead are selected
    query = sa.text(
        "SELECT id, title, question, answer, votes, recommendations, last_updated, enabled, category_id, team_id, \"order\" "
        "FROM helpdesk_kbitem"
    )
    # Use .all() to get a list of Row objects
    results = session.exec(query).all()

    # Convert each SQLAlchemy Row object to a dictionary and then validate with Pydantic model
    return [HelpdeskKBItemRead.model_validate(row._asdict()) for row in results]

@app.get("/search/", response_model=List[HelpdeskKBItemRead])
async def search_knowledge_base(*, phrase: str, session: Session = Depends(get_session)):
    try:
        # --- 1. First, try the precise database full-text search ---
        search_query = sa.text(
            "SELECT id, title, question, answer, votes, recommendations, last_updated, enabled, category_id, team_id, \"order\" "
            "FROM helpdesk_kbitem WHERE ts @@ phraseto_tsquery('english', :phrase)"
        )
        results = session.exec(search_query.params(phrase=phrase)).all()

        if results:
            print(f"Exact matches found for '{phrase}'.")
            return [HelpdeskKBItemRead.model_validate(row._asdict()) for row in results]
        
        # --- 2. If no results, use the new semantic search function ---
        print(f"No exact match for '{phrase}'. Using semantic search...")
        
        all_items_query = sa.text(
            "SELECT id, title, question, answer, votes, recommendations, last_updated, enabled, category_id, team_id, \"order\" "
            "FROM helpdesk_kbitem"
        )
        all_items_results = session.exec(all_items_query).all()
        all_items = [HelpdeskKBItemRead.model_validate(row._asdict()) for row in all_items_results]

        similar_results = find_similar_items_embeddings(phrase, all_items, top_n=5)
        
        return similar_results

    except Exception as e:
        print(f"Error during search: {e}")
        raise HTTPException(status_code=500, detail=f"Search error: {e}")
    
@app.put("/items/{item_id}", response_model=HelpdeskKBItemRead)
async def update_item(*, item_id: int, item_update: HelpdeskKBItemCreate, session: Session = Depends(get_session)):
    # Find the existing item in the database
    db_item = session.get(HelpdeskKBItem, item_id)
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")

    # Get the incoming data and update the database object's fields
    update_data = item_update.model_dump()
    for key, value in update_data.items():
        setattr(db_item, key, value)
        
    # Automatically update the last_updated timestamp to now
    db_item.last_updated = datetime.now(timezone.utc)

    try:
        session.add(db_item)
        session.commit()
        session.refresh(db_item)
        return db_item
    except Exception as e:
        session.rollback()
        # Log the full exception for debugging
        print(f"Error updating item: {e}")
        raise HTTPException(status_code=500, detail="Failed to update item.")


@app.delete("/items/{item_id}", response_model=dict)
async def delete_item(*, item_id: int, session: Session = Depends(get_session)):
    # Find the existing item in the database
    db_item = session.get(HelpdeskKBItem, item_id)
    if not db_item:
        raise HTTPException(status_code=404, detail="Item not found")
    
    try:
        session.delete(db_item)
        session.commit()
        return {"detail": "Item deleted successfully"}
    except Exception as e:
        session.rollback()
        # Log the full exception for debugging
        print(f"Error deleting item: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete item.")
