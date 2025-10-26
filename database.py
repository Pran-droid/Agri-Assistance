from pymongo import MongoClient

MONGO_URI = "mongodb://localhost:27017/"

def get_client():
    return MongoClient(MONGO_URI)

mongo_client = get_client()
db = mongo_client["farmer_assist_db"]
users_collection = db["users"]
