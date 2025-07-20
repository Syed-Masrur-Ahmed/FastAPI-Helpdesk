from fastapi import FastAPI, HTTPException, Depends
from typing import Optional, List, Generator
import sqlalchemy as sa
from sqlmodel import Field, SQLModel, create_engine, Session, select
import os
from dotenv import load_dotenv 
from datetime import datetime, timezone
import re
from nltk.corpus import stopwords
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from sentence_transformers import SentenceTransformer, util
import torch

# --- This function uses a pre-trained model ---
def find_similar_items_embeddings(phrase: str, all_items: list, top_n: int = 5):
    if not all_items:
        return []

    # --- 1. Load a pre-trained model ---
    print("Loading sentence-transformer model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("Model loaded.")

    # --- 2. Create the corpus of text to compare against ---
    corpus = [item.title + " " + item.question + " " + item.answer for item in all_items]

    # --- 3. Generate embeddings for the corpus and the search phrase ---
    # An embedding is the numerical vector that represents the meaning of the text.
    print("Generating embeddings for database items...")
    corpus_embeddings = model.encode(corpus, convert_to_tensor=True)
    
    print("Generating embedding for the search phrase...")
    phrase_embedding = model.encode(phrase, convert_to_tensor=True)

    # --- 4. Calculate cosine similarity between the phrase and all items ---
    # This is done very efficiently using the sentence-transformers utility function.
    print("Calculating similarity scores...")
    cosine_scores = util.cos_sim(phrase_embedding, corpus_embeddings)

    # --- 5. Find the top N most similar items ---
    # The 'top_k' parameter gives us the top N results directly.
    # The output is a list of tuples, each containing (score, corpus_index).
    top_results = torch.topk(cosine_scores, k=min(top_n, len(all_items)))

    # --- 6. Collect and return the results ---
    similar_items = []
    print("\nTop similarity scores:")
    for score, idx in zip(top_results[0][0], top_results[1][0]):
        item_index = idx.item()
        print(f"  - Score: {score:.4f}, Item: '{all_items[item_index].question[:60]}...'")
        similar_items.append(all_items[item_index])

    return similar_items

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

class HelpdeskKBItemBase(SQLModel):
    title: str = Field(max_length=255)
    question: str
    answer: str
    votes: int = Field(default=0)
    recommendations: int = Field(default=0)
    last_updated: datetime
    category_id: int
    enabled: bool = Field(default=True)
    team_id: Optional[int] = None
    order: Optional[int] = None

class HelpdeskKBItem(HelpdeskKBItemBase, table=True):
    __tablename__ = "helpdesk_kbitem"
    id: Optional[int] = Field(default=None, primary_key=True)


class HelpdeskKBItemCreate(HelpdeskKBItemBase):
    pass

class HelpdeskKBItemRead(HelpdeskKBItemBase):
    id: int 


app = FastAPI()


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

        # Call the new function
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
