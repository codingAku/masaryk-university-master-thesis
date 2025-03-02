import io
import streamlit as st
import subprocess
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

# Set page config as the very first Streamlit command
st.set_page_config(layout="wide", page_title="Eliciation meeting")

# Add margin between buttons without increasing font size and add padding between radio options
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

# Define a profile avatar URL to be used for both the left column and bot messages.
profile_avatar_url = "https://suz.vse.cz/wp-content/uploads/palach_deska.jpg"

# -----------------------------
# 1. Function to fetch available models via ollama list command
# -----------------------------
def get_available_models():
    try:
        output = subprocess.check_output(["ollama", "list"], universal_newlines=True)
        # Parse output: assume the first column of non-header lines is the model name.
        models = []
        for line in output.splitlines():
            # Skip empty lines and headers (adjust this logic as needed)
            if line.strip() and not line.startswith("NAME"):
                models.append(line.strip().split()[0])
        return models if models else ["llama3.1:8b"]
    except Exception as e:
        # In case of any error, fallback to a default model.
        return ["llama3.1:8b"]

# -----------------------------
# 2. Session State Setup
# -----------------------------
if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "persona" not in st.session_state:
    st.session_state["persona"] = {"name": "John Doe", "job": "Software Engineer"}
if "input_counter" not in st.session_state:
    st.session_state["input_counter"] = 0
if "selected_model" not in st.session_state:
    st.session_state["selected_model"] = "llama3.1:8b"
if "model" not in st.session_state:
    st.session_state["model"] = ChatOllama(model=st.session_state["selected_model"])

# Define mock users for selection
mock_users = {
    "John Doe": {"name": "John Doe", "job": "Software Engineer"},
    "Jane Smith": {"name": "Jane Smith", "job": "Data Scientist"},
}

# -----------------------------
# 3. Helper Functions
# -----------------------------
system_message = SystemMessagePromptTemplate.from_template(
    "You are {persona_name}, a helpful AI with the job title: {persona_job}. Respond concisely."
)

def build_prompt_messages():
    """Build the conversation prompt messages using the system prompt and history."""
    sys_msg = system_message.format(
        persona_name=st.session_state["persona"]["name"],
        persona_job=st.session_state["persona"]["job"]
    )
    prompt_msgs = [sys_msg]
    for entry in st.session_state["chat_history"]:
        prompt_msgs.append(HumanMessagePromptTemplate.from_template(entry["user"]))
        prompt_msgs.append(AIMessagePromptTemplate.from_template(entry["assistant"]))
    return ChatPromptTemplate.from_messages(prompt_msgs)

def generate_response(user_text):
    """Generate a response from ChatOllama using Langchain."""
    chat_prompt = build_prompt_messages()
    new_user_msg = HumanMessagePromptTemplate.from_template(user_text)
    chat_prompt.messages.append(new_user_msg)
    chain = chat_prompt | st.session_state["model"] | StrOutputParser()
    response = chain.invoke({})
    return response

def process_message(user_text):
    """Process a text message (from text input)."""
    if not user_text.strip():
        st.warning("Please enter a message before sending.")
        return
    response_text = generate_response(user_text)
    st.session_state["chat_history"].append({"user": user_text, "assistant": response_text})

def on_text_submit():
    """Called when the Send action is triggered (via text input's on_change)."""
    user_text = st.session_state.get("user_input")
    process_message(user_text)
    st.session_state["input_counter"] += 1
    st.session_state["user_input"] = ""  # clear the text input

def delete_chat():
    """Clear the entire chat history."""
    st.session_state["chat_history"] = []

def update_user():
    """Update persona based on radio button selection and clear chat history."""
    st.session_state["persona"] = mock_users[st.session_state["user_choice"]]
    st.session_state["chat_history"] = []  # clear chat window

def update_model():
    """Update model based on dropdown selection and clear chat history."""
    st.session_state["model"] = ChatOllama(model=st.session_state["selected_model"])
    st.session_state["chat_history"] = []  # clear chat when model changes

# -----------------------------
# 4. UI Layout
# -----------------------------
# Two columns: left (persona info, photo, and user selection) and right (chat area)
left_col, right_col = st.columns([2, 5], gap="medium")

# -- LEFT COLUMN: Persona, Photo & User Selection --
with left_col:
    # Horizontal layout: photo to the left, name and title to the right.
    photo_col, text_col = st.columns([1, 2])
    with photo_col:
        st.image(profile_avatar_url, width=100)
    with text_col:
        st.header(f"{st.session_state['persona']['name']}")
        st.subheader(f"{st.session_state['persona']['job']}")
    
    st.markdown("---")
    
    # User selection via radio buttons with on_change to update user info and clear chat
    st.radio("Select User:", options=list(mock_users.keys()), key="user_choice", on_change=update_user)

# -- RIGHT COLUMN: Chat Interface with Model Selection Dropdown --
with right_col:
    # Dropdown for model selection at the top right.
    available_models = get_available_models()
    st.selectbox("Select Model:", options=available_models, key="selected_model", on_change=update_model)
    
    st.button("Delete Chat", on_click=delete_chat, help="Clears the entire chat.")
    
    # Chat messages container (without a placeholder title or duplicate header)
    chat_placeholder = st.empty()
    with chat_placeholder.container():
        if st.session_state["chat_history"]:
            for i, exchange in enumerate(st.session_state["chat_history"]):
                # User messages: using default avatar style "no-avatar" for no image.
                message(exchange["user"], is_user=True, key=f"{i}_user", avatar_style="no-avatar")
                # Bot messages: display the profile picture using the logo parameter.
                message(exchange["assistant"], key=f"{i}", allow_html=True, logo=profile_avatar_url)
        else:
            st.write("No messages yet. Start the conversation below.")
    
    # Text input for user messages with on_change trigger for sending
    st.text_input("User Input:", key="user_input", on_change=on_text_submit)
