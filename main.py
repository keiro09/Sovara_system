from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
from dotenv import load_dotenv
from bson import ObjectId
import os
import psycopg
import redis
import json

load_dotenv()


app = FastAPI(
    title="Sovara",
    description="Sovara Social Memory Platform API",
    version="1.0.0"
)


redis_client = redis.Redi(
    host="redis",
    port=6379,
    decode_responses=True
)

MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI)

POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")

def get_postgres_connection():
    return psycopg.connect(
        host="postgres",
        port=5432,
        dbname="sovara",
        user="sovara_user",
        password=POSTGRES_PASSWORD
    )


db = client["Sovara"]
memories_collection = db["memories"]


class Memory(BaseModel):
    title: str
    content: str
    is_private: bool = False


class User(BaseModel):
    username: str



@app.post("/memories")
def create_memory(memory: Memory):
    result = memories_collection.insert_one({
        "title": memory.title,
        "content": memory.content,
        "is_private": memory.is_private
    })

    # Clear the cache after saving a new memory
    redis_client.delete("sovara:memories")

    return {
        "message": "Memory saved!",
        "id": str(result.inserted_id)
    }



@app.get("/")
def home():
    return {"message": "Welcome to Sovara!"}


@app.get("/test-postgres")
def test_postgres():
    try:
        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_user")
                result = cur.fetchone()

        return {
            "message": "PostgreSQL connected successfully!",
            "database": result[0],
            "user": result[1]
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"PostgreSQL connection failed: {str(e)}"
        )


@app.get("/test-redis")
def test_redis():
    try:
        redis_client.set("sovara_test", "Redis is working!")
        result = redis_client.get("sovara_test")

        return {
            "message": "Redis connected successfully!",
            "test_value": result
        }

    except redis.RedisError:
        raise HTTPException(
            status_code=500,
            detail="Could not connect to Redis."
        )


@app.post("/users")
def create_user(user: User):
    try:
        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (username)
                    VALUES (%s)
                    RETURNING id, username, created_at
                    """,
                    (user.username,)
                )
                new_user = cur.fetchone()

        return {
            "message": "User created successfully!",
            "id": new_user[0],
            "username": new_user[1],
            "created_at": new_user[2]
        }

    except psycopg.errors.UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="That username already exists."
        )



@app.get("/memories")
def get_memories():
    try:
        cached_memories = redis_client.get("sovara:memories")

        if cached_memories is not None:
            return {
                "source": "redis_cache",
                "memories": json.loads(cached_memories)
            }

        memories = list(memories_collection.find())

        for memory in memories:
            memory["_id"] = str(memory["_id"])

        redis_client.setex(
            "sovara:memories",
            60,
            json.dumps(memories)
        )

        return {
            "source": "mongodb",
            "memories": memories
        }

    except redis.RedisError:
        memories = list(memories_collection.find())

        for memory in memories:
            memory["_id"] = str(memory["_id"])

        return {
            "source": "mongodb",
            "memories": memories
        }


    
@app.get("/search")
def search_memories(keyword: str):
    memories = list(memories_collection.find({
        "$and": [
            {"is_private": {"$ne": True}},
            {
                "$or": [
                    {"title": {"$regex": keyword, "$options": "i"}},
                    {"content": {"$regex": keyword, "$options": "i"}}
                ]
            }
        ]
    }))

    for memory in memories:
        memory["_id"] = str(memory["_id"])

    return memories



@app.delete("/memories/{memory_id}")
def delete_memory(memory_id: str):
    if not ObjectId.is_valid(memory_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid memory ID"
        )

    result = memories_collection.delete_one({
        "_id": ObjectId(memory_id)
    })

    if result.deleted_count == 0:
        raise HTTPException(
            status_code=404,
            detail="Memory not found"
        )

    # Clear the feed cache
    redis_client.delete("sovara:memories")

    # Record the deletion in PostgreSQL
    try:
        with get_postgres_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO memory_audit_log
                        (memory_id, action, status)
                    VALUES (%s, %s, %s)
                    """,
                    (memory_id, "DELETE", "SUCCESS")
                )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Memory was deleted, but audit logging failed."
        )

    return {
        "message": "Memory deleted successfully",
        "id": memory_id,
        "audit_logged": True
    }



@app.get("/users")
def get_users():
    try:
        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, username, created_at FROM users ORDER BY id"
                )
                users = cur.fetchall()

        return [
            {
                "id": row[0],
                "username": row[1],
                "created_at": row[2]
            }
            for row in users
        ]

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Could not retrieve users."
        )


@app.put("/users/{user_id}")
def update_user(user_id: int, user: User):
    try:
        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE users
                    SET username = %s
                    WHERE id = %s
                    RETURNING id, username, created_at
                    """,
                    (user.username, user_id)
                )
                updated_user = cur.fetchone()

                if updated_user is None:
                    raise HTTPException(
                        status_code=404,
                        detail="User not found."
                    )

        return {
            "message": "Username updated successfully!",
            "id": updated_user[0],
            "username": updated_user[1],
            "created_at": updated_user[2]
        }

    except psycopg.errors.UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="That username already exists."
        )



@app.delete("/users/{user_id}")
def delete_user(user_id: int):
    try:
        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    DELETE FROM users
                    WHERE id = %s
                    RETURNING id, username
                    """,
                    (user_id,)
                )
                deleted_user = cur.fetchone()

                if deleted_user is None:
                    raise HTTPException(
                        status_code=404,
                        detail="User not found."
                    )

        return {
            "message": "User deleted successfully!",
            "id": deleted_user[0],
            "username": deleted_user[1]
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=500,
            detail="Could not delete user."
        )


@app.get("/sql-baseline-feed")
def sql_baseline_feed():
    with psycopg.connect(
        host="postgres",
        dbname="sovara",
        user="sovara_user",
        password=os.getenv("POSTGRES_PASSWORD")
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, content
                FROM baseline_memories
                ORDER BY id
            """)
            rows = cur.fetchall()

    return [
        {"id": row[0], "title": row[1], "content": row[2]}
        for row in rows
    ]