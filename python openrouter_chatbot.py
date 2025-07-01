import gradio as gr
import requests
import tiktoken
import time
import firebase_admin
from firebase_admin import credentials, db

# ✅ Firebase Setup
FIREBASE_CRED = "firebase_key.json"  # Ensure this file exists in the same directory
FIREBASE_DB_URL = "https://python-openrouter-chatbot-default-rtdb.firebaseio.com/"

# Initialize Firebase
if not firebase_admin._apps:
    cred = credentials.Certificate(FIREBASE_CRED)
    firebase_admin.initialize_app(cred, {
        'databaseURL': FIREBASE_DB_URL
    })

# 🔐 OpenRouter API Key
OPENROUTER_API_KEY = "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"

# ✅ Available Models
MODELS = [
    "mistralai/mistral-7b-instruct",
    "openchat/openchat-3.5-1210",
    "gryphe/mythomax-l2-13b"
]

# 🔢 Token Count Function
def count_tokens(text):
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return "Token count unavailable"

# 🤖 Chat Function using OpenRouter
def chat_openrouter(user_input, history, model_name):
    messages = [{"role": "system", "content": "You are a helpful assistant."}]
    for user, bot in history:
        messages.append({"role": "user", "content": user})
        messages.append({"role": "assistant", "content": bot})
    messages.append({"role": "user", "content": user_input})

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://chatbot.local",
                "X-Title": "GradioMistralBot"
            },
            json={
                "model": model_name,
                "messages": messages
            }
        )

        result = response.json()
        if "choices" not in result:
            return f"[❌ Error] API Response: {result}"

        reply = result["choices"][0]["message"]["content"]
        token_info = f"\n\n🔢 Token Usage:\nUser: {count_tokens(user_input)} | Reply: {count_tokens(reply)}"
        return reply + token_info

    except Exception as e:
        return f"[❗ Exception] {e}"

# 📤 Save to Firebase
def save_chat_to_firebase(chat_history, model_name):
    ref = db.reference("chats")
    timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")

    data = {
        "model": model_name,
        "timestamp": timestamp,
        "chat": []
    }

    for user, bot in chat_history:
        data["chat"].append({
            "user": user,
            "bot": bot
        })

    ref.push(data)
    return f"✅ Chat saved to Firebase at {timestamp}"

# 📥 Retrieve from Firebase (latest chat)
def retrieve_chat_from_firebase():
    ref = db.reference("chats")
    all_chats = ref.order_by_key().limit_to_last(1).get()

    if not all_chats:
        return "[📭 No previous chats found in Firebase.]"

    latest_chat = list(all_chats.values())[-1]
    chat_text = f"🕒 Timestamp: {latest_chat['timestamp']}\n🧠 Model: {latest_chat['model']}\n\n"
    for turn in latest_chat["chat"]:
        chat_text += f"👤 You: {turn['user']}\n🤖 Bot: {turn['bot']}\n\n"
    return chat_text

# 🎛️ Gradio UI
with gr.Blocks() as demo:
    gr.Markdown("## 🤖 OpenRouter Chatbot + Firebase Integration")

    chatbot = gr.Chatbot(label="💬 Conversation")
    msg = gr.Textbox(label="🗣️ Type your message")
    model_dropdown = gr.Dropdown(choices=MODELS, label="🧠 Choose Model", value=MODELS[0])
    clear = gr.Button("🔁 Clear Chat")
    save_btn = gr.Button("📤 Save Chat to Firebase")
    save_status = gr.Textbox(label="Status", interactive=False)

    state = gr.State([])

    # 🔄 Main Chat Logic
    def respond(message, chat_history, model):
        if "show history" in message.lower() or "retrieve from firebase" in message.lower():
            firebase_data = retrieve_chat_from_firebase()
            chat_history.append((message, firebase_data))
            return "", chat_history

        response = chat_openrouter(message, chat_history, model)
        chat_history.append((message, response))
        return "", chat_history

    def save_chat(history, model):
        return save_chat_to_firebase(history, model)

    # 🧠 Bindings
    msg.submit(respond, [msg, state, model_dropdown], [msg, chatbot])
    clear.click(lambda: ([], []), None, [state, chatbot])
    save_btn.click(save_chat, [state, model_dropdown], [save_status])

# 🚀 Launch
demo.launch()
