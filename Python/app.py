from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
from psycopg2 import sql
from contextlib import asynccontextmanager
import os

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Creates the 'items' table if it doesn't exist."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS items (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT
            );
        """)
        conn.commit()
        print("Table 'items' checked/created successfully.")
    except psycopg2.Error as e:
        print(f"Error creating table: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()
    yield

app = FastAPI(lifespan=lifespan)

DB_HOST = "localhost"
DB_PORT = "15432" 
DB_NAME = os.getenv("POSTGRES_DB", "test") 
DB_USER = os.getenv("POSTGRES_USER", "postgres")  
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")

# Fallback to default if .env not loaded (less ideal for production, but good for quick test)
if DB_NAME == "postgres":
    print("WARNING: Database credentials not properly loaded from .env. Using fallback defaults.")


# Pydantic model for request body validation
class Item(BaseModel):
    title: str
    question: str
    answer: str
    votes: int
    recommendations: int
    last_updated: str
    category_id: int
    enabled: bool

def get_db_connection():
    """Establishes and returns a database connection."""
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cur = conn.cursor()
        cur.execute("SELECT current_database();")
        connected_db_name = cur.fetchone()[0]
        print(f"Successfully connected to database: '{connected_db_name}' as user '{DB_USER}'")
        cur.close() 
        return conn
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        raise HTTPException(status_code=500, detail="Could not connect to the database.")


@app.post("/items/")
async def create_item(item: Item):
    """Creates a new item in the database."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            sql.SQL("INSERT INTO helpdesk_kbitem (title, question, answer, votes, recommendations, last_updated, enabled, category_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;"),
            (item.title, item.question, item.question, item.answer, item.votes, item.recommendations, item.last_updated, item.enabled, item.category_id)
        )
        item_id = cur.fetchone()[0]
        conn.commit()
        return {"id": item_id, **item.model_dump()}
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()

@app.get("/items/{item_id}")
async def read_item(item_id: int):
    """Retrieves an item by its ID."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            sql.SQL("SELECT id, title, question, answer FROM helpdesk_kbitem WHERE id = %s;"),
            (item_id)
        )
        item = cur.fetchone()
        if item is None:
            raise HTTPException(status_code=404, detail="Item not found")
        return {"id": item[0], "name": item[1], "description": item[2]}
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()

@app.get("/items/")
async def read_all_items():
    """Retrieves all items from the database."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(sql.SQL("SELECT id, title, question, answer FROM helpdesk_kbitem;"))
        items = []
        for row in cur.fetchall():
            items.append({"id": row[0], "title": row[1], "question": row[2], "answer": row[3]})
        return items
    except psycopg2.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    finally:
        if conn:
            cur.close()
            conn.close()
