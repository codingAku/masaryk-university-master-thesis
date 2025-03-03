import io
import streamlit as st
import subprocess
import base64
from PIL import Image
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import (
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    AIMessagePromptTemplate,
    ChatPromptTemplate,
)
from streamlit_chat import message  # new chat UI component
from streamlit.components.v1 import html

# Import our database helper functions from db.py
import db

st.set_page_config(layout="wide", page_title="STAKEBOT")

# Add padding between radio options
st.markdown(
    """
    <style>
    button {
        margin: 5px;
    }
    div[role="radiogroup"] > label {
        margin-bottom: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# -----------------------------
# 1. Get available models via ollama list command.
# -----------------------------
def get_available_models():
    try:
        output = subprocess.check_output(["ollama", "list"], universal_newlines=True)
        models = []
        for line in output.splitlines():
            if line.strip() and not line.startswith("NAME"):
                models.append(line.strip().split()[0])
        return models if models else ["llama3.1:latest"]
    except Exception as e:
        return ["llama3.1:latest"]

# -----------------------------
# 2. Session State Setup
# -----------------------------
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "persona" not in st.session_state:
    st.session_state["persona"] = {}  # No user selected initially.
if "input_counter" not in st.session_state:
    st.session_state["input_counter"] = 0
if "selected_model" not in st.session_state:
    st.session_state["selected_model"] = "llama3.1:latest"
if "model" not in st.session_state:
    st.session_state["model"] = ChatOllama(model=st.session_state["selected_model"])
if "show_add_user_form" not in st.session_state:
    st.session_state["show_add_user_form"] = False
if "user_choice" not in st.session_state:
    # Initially set to placeholder so no user is selected.
    st.session_state["user_choice"] = "-- Select a User --"

# -----------------------------
# 3. Helper Functions for Chat
# -----------------------------
system_message = SystemMessagePromptTemplate.from_template(
    "You are {persona_name}, a helpful AI with the job title: {persona_job}. Respond concisely."
)

def build_prompt_messages():
    persona_name = st.session_state["persona"].get("name", "User")
    persona_job = st.session_state["persona"].get("job", "N/A")
    sys_msg = system_message.format(persona_name=persona_name, persona_job=persona_job)
    prompt_msgs = [sys_msg]
    for entry in st.session_state["chat_history"]:
        prompt_msgs.append(HumanMessagePromptTemplate.from_template(entry["user"]))
        prompt_msgs.append(AIMessagePromptTemplate.from_template(entry["assistant"]))
    return ChatPromptTemplate.from_messages(prompt_msgs)

def generate_response(user_text):
    chat_prompt = build_prompt_messages()
    new_user_msg = HumanMessagePromptTemplate.from_template(user_text)
    chat_prompt.messages.append(new_user_msg)
    chain = chat_prompt | st.session_state["model"] | StrOutputParser()
    response = chain.invoke({})
    return response

def process_message(user_text):
    if not user_text.strip():
        st.warning("Please enter a message before sending.")
        return
    if not st.session_state["persona"].get("id"):
        st.warning("No user selected. Please add or select a user.")
        return
    response_text = generate_response(user_text)
    person_id = st.session_state["persona"]["id"]
    # Save both messages to the database.
    db.add_chat_message(person_id, "user", user_text)
    db.add_chat_message(person_id, "assistant", response_text)
    st.session_state["chat_history"] = db.get_chat_history(person_id)

def on_text_submit():
    user_text = st.session_state.get("user_input")
    process_message(user_text)
    st.session_state["input_counter"] += 1
    st.session_state["user_input"] = ""  # Clear text input

def delete_chat():
    st.session_state["chat_history"] = []
    #TODO: delete from db.

def update_model():
    st.session_state["model"] = ChatOllama(model=st.session_state["selected_model"])

# -----------------------------
# 4. Database Helper Functions for Users
# -----------------------------
def get_db_users():
    return db.get_users()

def update_persona(new_persona):
    st.session_state["persona"] = new_persona
    if new_persona.get("id"):
        st.session_state["chat_history"] = db.get_chat_history(new_persona["id"])
    else:
        st.session_state["chat_history"] = []

def show_add_user():
    st.session_state["show_add_user_form"] = True

def submit_new_user():
    first_name = st.session_state.get("first_name")
    last_name = st.session_state.get("last_name")
    job_title = st.session_state.get("job_title")
    native_language = st.session_state.get("native_language")
    english_level = st.session_state.get("english_level")
    personality_traits = st.session_state.get("personality_traits")
    profile_photo_file = st.session_state.get("profile_photo")
    transcript_file = st.session_state.get("transcript_file")
    profile_photo_bytes = profile_photo_file.read() if profile_photo_file is not None else None
    transcript_bytes = transcript_file.read() if transcript_file is not None else None
    new_person = db.add_user(first_name, last_name, job_title, native_language, english_level, personality_traits, profile_photo_bytes, transcript_bytes)
    st.success("New user added successfully!")
    new_user = {
        "id": new_person.id,
        "name": f"{first_name} {last_name}",
        "job": job_title,
        "profile_photo": new_person.profile_photo
        #TODO: add other fields
    }
    st.session_state["show_add_user_form"] = False

def image_to_base64(image_bytes):
    return f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"

# -----------------------------
# 5. UI Layout
# -----------------------------
# Two columns: LEFT for user management, RIGHT for chat.
left_col, right_col = st.columns([2, 5], gap="medium")

# LEFT COLUMN: User management.
with left_col:
    if st.session_state["show_add_user_form"]:
        st.header("Add New User")
        with st.form("add_user_form"):
            st.text_input("First Name:", key="first_name")
            st.text_input("Last Name:", key="last_name")
            st.text_input("Job Title:", key="job_title")
            st.text_input("Native Language:", key="native_language")
            st.text_input("English Level:", key="english_level")
            st.text_area("Personality Traits:", key="personality_traits")
            st.file_uploader("Upload a Profile Photo:", key="profile_photo", type=["png", "jpg", "jpeg"])
            st.file_uploader("Upload Transcript (txt):", key="transcript_file", type=["txt"])
            st.form_submit_button("Save", on_click=submit_new_user)
    else:
        if st.session_state["persona"]:
            # Display user info from DB, including profile photo if available.
            photo_col, text_col = st.columns([1, 2])
            with photo_col:
                profile_photo = st.session_state["persona"].get("profile_photo")
                if profile_photo:
                    try:
                        # Convert bytes to an image
                        image = Image.open(io.BytesIO(profile_photo))

                        # Display image as a circle using Streamlit
                        st.markdown(
                            """
                            <style>
                            .circle-img {
                                border-radius: 100%;
                                width: 100px;
                                height: 100px;
                                object-fit: cover;
                                display: block;
                                margin: auto;
                            }
                            </style>
                            """,
                            unsafe_allow_html=True
                        )
                        st.image(image, width=100)
                    except Exception as e:
                        st.error(f"Error loading image: {e}")
            with text_col:
                st.header(st.session_state["persona"]["name"])
                st.subheader(st.session_state["persona"]["job"])
        else:
            st.info("No user selected. Please add a user.")
        st.markdown("---")
        # Load users from the database.
        db_users = get_db_users()
        if db_users:
            user_options = {user["name"]: user for user in db_users}  # Map user names to user objects

            # Ensure no default selection
            st.session_state.setdefault("user_choice", None)

            selected_user = st.selectbox(
                "Select User:",
                options=["-- Select a User --"] + list(user_options.keys()),  # Placeholder at the top
                index=0,  # Default to "-- Select a User --"
                key="user_choice",
                on_change=lambda: update_persona(user_options.get(st.session_state["user_choice"], {}))
            )
        else:
            st.info("No users found. Please add a user.")

        st.button("Add User", on_click=show_add_user)

# RIGHT COLUMN: Chat interface.
with right_col:
    available_models = get_available_models()
    st.selectbox("Select Model:", options=available_models, key="selected_model", on_change=update_model)
    st.button("Delete Chat", on_click=delete_chat, help="Clears the entire chat.")
    chat_placeholder = st.empty()
    with chat_placeholder.container():
        if st.session_state["chat_history"]:
            for i, exchange in enumerate(st.session_state["chat_history"]):
                message(exchange["user"], is_user=True, key=f"{i}_user", avatar_style="no-avatar")
                if st.session_state["persona"].get("profile_photo"):
                    logo_url = image_to_base64(st.session_state["persona"]["profile_photo"])
                else:
                    logo_url = None
                message(exchange["assistant"], key=f"{i}", allow_html=True, logo=logo_url, avatar_style="no-avatar")
        else:
            st.write("No messages yet. Start the conversation below.")
    if st.session_state["persona"].get("id"):
        st.text_input("User Input:", key="user_input", on_change=on_text_submit)
    else:
        st.info("Chat disabled. Please add or select a user to start chatting.")
