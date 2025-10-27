# from datetime import datetime
import datetime
from functools import wraps
import time
import json

from dotenv import load_dotenv
from flask import Flask, jsonify, redirect, render_template, request, session, url_for, Response, stream_with_context

from models import (
    append_chat_messages,
    create_chat,
    create_user,
    delete_chat,
    ensure_chat_containers,
    find_user_by_credentials,
    find_user_by_email,
    get_chat_by_id,
    get_user_by_id,
    update_chat_title,
    update_user_crops,
    update_user_language,
    update_user_location,
)
from services import handle_intents, translate_text
from services.chat_logic import handle_intents_stream


load_dotenv()

app = Flask(__name__)
app.secret_key = "dev_secret_key_change_me"

LANGUAGE_CHOICES = [
    ("en", "English"),
    ("hi", "Hindi"),
    ("mr", "Marathi"),
    ("ta", "Tamil"),
    ("te", "Telugu"),
]


def login_required(view_function):
    """Simple decorator to ensure a user session exists before accessing a route."""

    @wraps(view_function)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view_function(*args, **kwargs)

    return wrapper


@app.context_processor
def inject_auth_state():
    return {
        "is_authenticated": "user_id" in session,
        "current_user": get_logged_in_user()
    }


@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("chat"))
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        location = request.form.get("location", "").strip()
        preferred_language = request.form.get("preferred_language", "en")
        password = request.form.get("password", "")

        if not all([name, email, location, preferred_language, password]):
            error = "All fields are required."
        elif find_user_by_email(email):
            error = "An account with this email already exists."
        else:
            user_doc = {
                "name": name,
                "email": email,
                "location": location,
                "preferred_language": preferred_language,
                "password": password,
                "crops": [],
                "created_at": datetime.datetime.now(datetime.UTC),
            }
            create_user(user_doc)
            return redirect(url_for("login"))

    return render_template("signup.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = find_user_by_credentials(email, password)
        if user:
            session["user_id"] = str(user["_id"])
            return redirect(url_for("profile"))
        error = "Invalid email or password."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/market-prices")
def market_prices():
    """Display live market prices from data.gov.in API"""
    return render_template("market_prices.html")


@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = get_logged_in_user()
    if not user:
        return redirect(url_for("login"))

    message = None
    message_class = None
    if request.method == "POST":
        new_location = request.form.get("location", "").strip()
        new_language = request.form.get("preferred_language", "").strip() or user.get("preferred_language", "en")
        crops_text = request.form.get("crops", "").strip()

        updates_applied = []

        if new_location and new_location != user.get("location"):
            if update_user_location(user["_id"], new_location):
                updates_applied.append("Location updated.")

        if new_language and new_language != user.get("preferred_language"):
            if update_user_language(user["_id"], new_language):
                updates_applied.append("Preferred language updated.")

        crops_list = [item.strip() for item in crops_text.split(",") if item.strip()]
        existing_crops = user.get("crops") or []
        if crops_list != existing_crops:
            if update_user_crops(user["_id"], crops_list):
                updates_applied.append("Crops updated.")

        if updates_applied:
            message = " ".join(updates_applied)
            message_class = "alert-success"
        else:
            message = "No changes detected."
            message_class = "alert-info"

        user = get_logged_in_user()

    language_options = list(LANGUAGE_CHOICES)
    preferred_language = user.get("preferred_language") if user else None
    if preferred_language and preferred_language not in {code for code, _ in language_options}:
        language_options.append((preferred_language, preferred_language.upper()))

    return render_template(
        "profile.html",
        user=user,
        language_choices=language_options,
        message=message,
        message_class=message_class,
    )


@app.route("/chat")
@login_required
def chat():
    user = get_logged_in_user()
    if not user:
        return redirect(url_for("login"))

    chat_id = request.args.get("chat_id", "").strip()
    chats = user.get("chats", []) or []

    chats_sorted = sorted(
        chats,
        key=lambda c: c.get("updated_at") or c.get("created_at") or datetime.min,
        reverse=True,
    )

    active_chat = None
    if chat_id:
        active_chat = get_chat_by_id(user, chat_id)
    if not active_chat and chats_sorted:
        active_chat = chats_sorted[0]

    return render_template(
        "chat.html",
        user=user,
        chats=chats_sorted,
        active_chat=active_chat,
    )


@app.route("/get_response", methods=["POST"])
@login_required
def get_response():
    # Start timing
    start_time = time.time()
    
    payload = request.get_json(silent=True) or {}
    user_message_original = (payload.get("message") or "").strip()
    requested_chat_id = (payload.get("chat_id") or "").strip()

    if not user_message_original:
        return jsonify({"response": "Please enter a message."}), 400

    user = get_logged_in_user()
    if not user:
        return jsonify({"response": "User not found."}), 404

    user = ensure_chat_containers(user)
    chat = None
    if requested_chat_id:
        chat = get_chat_by_id(user, requested_chat_id)

    if not chat:
        chat = create_chat(user["_id"])
        requested_chat_id = chat["chat_id"]

    # Database operations complete
    db_time = time.time()
    print(f"⏱️  Database query took: {db_time - start_time:.4f} seconds")

    # Get user's preferred language
    user_lang = user.get("preferred_language", "en")
    
    # Translate incoming message to English if needed
    english_message = user_message_original
    if user_lang and user_lang != "en":
        try:
            english_message = translate_text(user_message_original, src_language=user_lang, dest_language="en")
        except Exception as e:
            print(f"Translation error (user->en): {e}")
            english_message = user_message_original

    # Call to AI service with English message
    bot_response = handle_intents(user, english_message)
    
    # Translate response back to user's language
    final_response = bot_response
    if user_lang and user_lang != "en":
        try:
            final_response = translate_text(bot_response, src_language="en", dest_language=user_lang)
        except Exception as e:
            print(f"Translation error (en->user): {e}")
            final_response = bot_response

    # AI call complete
    api_time = time.time()
    print(f"⏱️  Gemini API call took: {api_time - db_time:.4f} seconds")

    chat_entries = [
        {"sender": "user", "message": user_message_original, "timestamp": datetime.datetime.now(datetime.UTC)},
        {"sender": "bot", "message": final_response, "timestamp": datetime.datetime.now(datetime.UTC)},
    ]

    was_empty = not chat.get("messages")
    chat_title = chat.get("title", "New Chat")
    append_chat_messages(user["_id"], requested_chat_id, chat_entries)

    if was_empty:
        inferred_title = user_message_original[:60] or "New Chat"
        update_chat_title(user["_id"], requested_chat_id, inferred_title)
        chat["title"] = inferred_title
        chat_title = inferred_title

    # Total time
    total_time = time.time()
    print(f"⏱️  Total request took: {total_time - start_time:.4f} seconds")
    print(f"📊 Breakdown: DB={db_time-start_time:.4f}s, API={api_time-db_time:.4f}s, Save={total_time-api_time:.4f}s")

    return jsonify({
        "response": final_response,
        "chatId": requested_chat_id,
        "chatTitle": chat_title,
    })


@app.route("/chat_stream", methods=["POST"])
@login_required
def chat_stream():
    """Streaming endpoint for real-time AI responses."""
    try:
        request_start = time.time()
        
        payload = request.get_json(silent=True) or {}
        user_message_original = (payload.get("message") or "").strip()
        requested_chat_id = (payload.get("chat_id") or "").strip()

        if not user_message_original:
            return jsonify({"error": "Please enter a message."}), 400

        user = get_logged_in_user()
        if not user:
            return jsonify({"error": "User not found."}), 404

        user = ensure_chat_containers(user)
        chat = None
        if requested_chat_id:
            chat = get_chat_by_id(user, requested_chat_id)

        if not chat:
            chat = create_chat(user["_id"])
            requested_chat_id = chat["chat_id"]

        db_end = time.time()
        db_duration = db_end - request_start
        print(f"⏱️  Database query took: {db_duration:.4f} seconds")

        # Get user's preferred language
        user_lang = user.get("preferred_language", "en")
        
        # Translate incoming message to English if needed
        english_message = user_message_original
        if user_lang and user_lang != "en":
            try:
                english_message = translate_text(user_message_original, src_language=user_lang, dest_language="en")
            except Exception as e:
                print(f"Translation error (user->en): {e}")
                english_message = user_message_original

        def generate():
            """Generator function for streaming response."""
            # Send immediate acknowledgment to start the stream
            yield f": connected\n\n"
            
            full_response = []
            api_start = time.time()
            
            # Stream the response chunk by chunk (includes PDF context retrieval + Gemini API)
            for chunk in handle_intents_stream(user, english_message):
                # Translate each chunk to user's language before sending
                translated_chunk = chunk
                if user_lang and user_lang != "en":
                    try:
                        translated_chunk = translate_text(chunk, src_language="en", dest_language=user_lang)
                    except Exception as e:
                        print(f"Translation error for chunk: {e}")
                        translated_chunk = chunk
                
                full_response.append(translated_chunk)
                # Send each chunk as Server-Sent Events (SSE) format immediately
                chunk_data = f"data: {json.dumps({'text': translated_chunk})}\n\n"
                yield chunk_data
            
            api_end = time.time()
            api_duration = api_end - api_start
            print(f"⏱️  Gemini API call took: {api_duration:.4f} seconds")
            
            # After streaming is complete, save to database
            save_start = time.time()
            final_response = "".join(full_response)
            
            chat_entries = [
                {"sender": "user", "message": user_message_original, "timestamp": datetime.datetime.now(datetime.UTC)},
                {"sender": "bot", "message": final_response, "timestamp": datetime.datetime.now(datetime.UTC)},
            ]

            was_empty = not chat.get("messages")
            append_chat_messages(user["_id"], requested_chat_id, chat_entries)

            if was_empty:
                inferred_title = user_message_original[:60] or "New Chat"
                update_chat_title(user["_id"], requested_chat_id, inferred_title)
                chat_title = inferred_title
            else:
                chat_title = chat.get("title", "New Chat")
            
            save_end = time.time()
            save_duration = save_end - save_start
            total_duration = save_end - request_start
            
            print(f"⏱️  Total request took: {total_duration:.4f} seconds")
            print(f"📊 Breakdown: DB={db_duration:.4f}s, API={api_duration:.4f}s, Save={save_duration:.4f}s")
            
            # Send completion signal with metadata
            yield f"data: {json.dumps({'done': True, 'chatId': requested_chat_id, 'chatTitle': chat_title})}\n\n"

        response = Response(stream_with_context(generate()), mimetype='text/event-stream')
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['X-Accel-Buffering'] = 'no'
        return response

    except Exception as e:
        print(f"Error in chat_stream: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/chat/new", methods=["POST"])
@login_required
def create_new_chat():
    user = get_logged_in_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    new_chat = create_chat(user["_id"])
    return jsonify({
        "chatId": new_chat["chat_id"],
        "title": new_chat.get("title", "New Chat"),
    })


@app.route("/chat/delete", methods=["POST"])
@login_required
def delete_chat():
    user = get_logged_in_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    payload = request.get_json(silent=True) or {}
    chat_id = (payload.get("chat_id") or "").strip()

    if not chat_id:
        return jsonify({"error": "Chat ID is required."}), 400

    from models import delete_chat as delete_chat_model
    success = delete_chat_model(user["_id"], chat_id)
    if success:
        return jsonify({"success": True})
    else:
        return jsonify({"error": "Failed to delete chat."}), 400


def get_logged_in_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = get_user_by_id(user_id)
    if not user:
        return None
    return ensure_chat_containers(user)


if __name__ == "__main__":
    app.run(debug=True)
