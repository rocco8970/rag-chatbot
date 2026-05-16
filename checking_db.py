import psycopg2
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

try:
    conn = psycopg2.connect(
        dbname="postgres",
        user="postgres",
        password=os.getenv("DB_PASSWORD", ""),
        host="localhost",
        port="5432"
    )

    print("Database connected successfully!")

    conn.close()

except Exception as e:
    print("Error:", e)