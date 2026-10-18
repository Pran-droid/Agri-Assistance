import os
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("MONGO_DB_NAME", "farmer_assist_db")


def get_client():
    return MongoClient(MONGO_URI)


mongo_client = get_client()
db = mongo_client[DB_NAME]
users_collection = db["users"]

