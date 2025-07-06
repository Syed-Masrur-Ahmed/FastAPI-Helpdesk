import psycopg2
from psycopg2 import sql
from psycopg2.extras import execute_batch # For efficient batch inserts
import random
from faker import Faker

DB_HOST = "localhost"
DB_PORT = "15432" 
DB_NAME = "test"
DB_USER = "postgres"
DB_PASSWORD = "password"

if not all([DB_NAME, DB_USER, DB_PASSWORD]):
    print("ERROR: Database credentials (POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD) not found in .env file or environment variables.")
    exit(1)

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        print(f"Connected to database: '{DB_NAME}' as user '{DB_USER}'")
        return conn
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        exit(1) # Exit if connection fails

def generate_and_insert_kb_data(num_items, batch_size):
    fake = Faker()
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Prepare the INSERT statement template
        insert_query = sql.SQL("INSERT INTO helpdesk_kbitem (title, question, answer, votes, recommendations, last_updated, enabled, category_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s);")

        data_to_insert = []
        print(f"Generating and inserting {num_items} mock helpdesk KB items...")
        for i in range(num_items):
            # Generate fake data for your helpdesk_kbitems columns
            kb_title = fake.sentence(nb_words=random.randint(4, 10)).replace('.', '')
            kb_question = fake.paragraph(nb_sentences=random.randint(2, 4))
            kb_answer = fake.paragraph(nb_sentences=random.randint(4, 6))
            kb_votes = random.randint(0,50)
            kb_recommendations = random.randint(0,30)
            kb_last_updated = '2024-07-06 10:00:00-04'
            kb_category_id = 1
            # kb_team_id = random.randint(1,5)
            # kb_order = i + 1
            kb_enabled = random.choice([True, False])

            data_to_insert.append((kb_title, kb_question, kb_answer, kb_votes, kb_recommendations,
                                   kb_last_updated, kb_enabled, kb_category_id))

            if len(data_to_insert) >= batch_size:
                execute_batch(cur, insert_query, data_to_insert)
                conn.commit()
                print(f"  Inserted {i + 1} items so far...")
                data_to_insert = [] # Clear the batch list

        # Insert any remaining items in the last batch
        if data_to_insert:
            execute_batch(cur, insert_query, data_to_insert)
            conn.commit()
            print(f"  Inserted final {len(data_to_insert)} items.")

        print(f"Successfully inserted {num_items} mock helpdesk KB items into '{DB_NAME}'.")

    except psycopg2.Error as e:
        print(f"Error during data insertion: {e}")
        if conn:
            conn.rollback() 
    finally:
        if conn:
            cur.close()
            conn.close()

if __name__ == "__main__":
    num_items = int(input("num_items: "))
    batch_size = int(input("batch_size: "))
    generate_and_insert_kb_data(num_items=num_items, batch_size=batch_size) 