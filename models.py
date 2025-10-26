from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId

from database import users_collection


def build_new_chat(title: str = "New Chat") -> Dict[str, Any]:
    now = datetime.utcnow()
    return {
        "chat_id": str(ObjectId()),
        "title": title,
        "created_at": now,
        "updated_at": now,
        "messages": [],
    }


def create_user(user_data: Dict[str, Any]) -> None:
    user_data.setdefault("chats", [build_new_chat()])
    users_collection.insert_one(user_data)


def find_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    return users_collection.find_one({"email": email})


def find_user_by_credentials(email: str, password: str) -> Optional[Dict[str, Any]]:
    return users_collection.find_one({"email": email, "password": password})


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    try:
        mongo_id = ObjectId(user_id)
    except Exception:
        return None
    return users_collection.find_one({"_id": mongo_id})


def ensure_chat_containers(user: Dict[str, Any]) -> Dict[str, Any]:
    chats = user.get("chats")
    if isinstance(chats, list) and chats:
        return user

    existing_history = user.get("chat_history", [])
    if existing_history:
        chat = build_new_chat("Conversation")
        chat["messages"] = existing_history
        chat["updated_at"] = existing_history[-1].get("timestamp", datetime.utcnow())
        chats = [chat]
    else:
        chats = [build_new_chat()]

    users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"chats": chats}, "$unset": {"chat_history": ""}}
    )
    user["chats"] = chats
    return user


def create_chat(user_id: ObjectId, title: Optional[str] = None) -> Dict[str, Any]:
    chat = build_new_chat(title or "New Chat")
    users_collection.update_one(
        {"_id": user_id},
        {
            "$push": {"chats": chat}
        }
    )
    return chat


def get_chat_by_id(user: Dict[str, Any], chat_id: str) -> Optional[Dict[str, Any]]:
    for chat in user.get("chats", []):
        if chat.get("chat_id") == chat_id:
            return chat
    return None


def update_user_location(user_id: ObjectId, new_location: str) -> bool:
    result = users_collection.update_one(
        {"_id": user_id},
        {"$set": {"location": new_location}}
    )
    return result.modified_count > 0


def update_user_crops(user_id: ObjectId, crops_list: List[str]) -> bool:
    result = users_collection.update_one(
        {"_id": user_id},
        {"$set": {"crops": crops_list}}
    )
    return result.modified_count > 0


def update_user_language(user_id: ObjectId, language: str) -> bool:
    result = users_collection.update_one(
        {"_id": user_id},
        {"$set": {"preferred_language": language}}
    )
    return result.modified_count > 0


def append_chat_messages(user_id: ObjectId, chat_id: str, entries: List[Dict[str, Any]]) -> None:
    timestamped_entries: List[Dict[str, Any]] = []
    for entry in entries:
        timestamped_entries.append({
            "sender": entry["sender"],
            "message": entry["message"],
            "timestamp": entry.get("timestamp", datetime.utcnow()),
        })
    users_collection.update_one(
        {"_id": user_id, "chats.chat_id": chat_id},
        {
            "$push": {"chats.$.messages": {"$each": timestamped_entries}},
            "$set": {"chats.$.updated_at": datetime.utcnow()},
        }
    )


def update_chat_title(user_id: ObjectId, chat_id: str, title: str) -> None:
    users_collection.update_one(
        {"_id": user_id, "chats.chat_id": chat_id},
        {"$set": {"chats.$.title": title.strip()[:80], "chats.$.updated_at": datetime.utcnow()}}
    )


def delete_chat(user_id: ObjectId, chat_id: str) -> bool:
    result = users_collection.update_one(
        {"_id": user_id},
        {"$pull": {"chats": {"chat_id": chat_id}}}
    )
    return result.modified_count > 0
