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
from streamlit_chat import message
from streamlit.components.v1 import html

# Import our database helper functions from db.py
import db_helpers

# Import helper modules
from model_helpers import get_available_models
from chat_helpers import (
    build_prompt_messages,
    generate_response,
    process_message,
    on_text_submit,
    delete_chat,
    update_model,
    image_to_base64,
)
from user_helpers import (
    get_db_users,
    update_persona,
    update_user,
    cancel_user_update,
    delete_user,
    submit_new_user,
    show_add_user,
)

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
    """,
    unsafe_allow_html=True,
)

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
if "update_mode" not in st.session_state:
    st.session_state["update_mode"] = False

# -----------------------------
# 5. UI Layout
# -----------------------------
# Two columns: LEFT for user management, RIGHT for chat.
left_col, right_col = st.columns([2, 5], gap="medium")

# LEFT COLUMN: User management.
with left_col:
    if st.session_state.get("show_add_user_form", False):
        st.header("Update/Add User")
        form = st.form("add_user_form")

        form.text_input(
            "First Name:",
            key="first_name",
            value=(
                st.session_state.get("persona", {}).get("first_name", "")
                if st.session_state.get("update_mode", False)
                else ""
            ),
        )

        form.text_input(
            "Last Name:",
            key="last_name",
            value=(
                st.session_state.get("persona", {}).get("last_name", "")
                if st.session_state.get("update_mode", False)
                else ""
            ),
        )

        form.text_input(
            "Job Title:",
            key="job_title",
            value=(
                st.session_state.get("persona", {}).get("job_title", "")
                if st.session_state.get("update_mode", False)
                else ""
            ),
        )

        form.text_input(
            "Native Language:",
            key="native_language",
            value=(
                st.session_state.get("persona", {}).get("native_language", "")
                if st.session_state.get("update_mode", False)
                else ""
            ),
        )

        form.text_input(
            "English Level:",
            key="english_level",
            value=(
                st.session_state.get("persona", {}).get("english_level", "")
                if st.session_state.get("update_mode", False)
                else ""
            ),
        )

        form.text_area(
            "Personality Traits:",
            key="personality_traits",
            value=(
                st.session_state.get("persona", {}).get("personality_traits", "")
                if st.session_state.get("update_mode", False)
                else ""
            ),
        )

        form.file_uploader(
            "Upload Profile Photo:",
            key="profile_photo",
            type=["png", "jpg", "jpeg"]
        )

        form.file_uploader(
            "Upload Transcripts:",
            key="transcript_files",
            type=["txt"],
            accept_multiple_files=True,
        )

        form.form_submit_button("Save", on_click=submit_new_user)
        form.form_submit_button("Cancel", on_click=cancel_user_update)

        if st.session_state.get("update_mode", False):
            form.form_submit_button("Delete User", on_click=delete_user)
    else:
        if st.session_state["persona"]:
            # Display user info from DB, including profile photo if available.
            photo_col, text_col = st.columns([1, 2])
            with photo_col:
                profile_photo = st.session_state["persona"].get("profile_photo")
                if profile_photo:
                    try:
                        # Convert bytes to an image
                        img_base64 = base64.b64encode(profile_photo).decode()

                        st.markdown(
                            f"""
                            <style>
                                .circle-img {{
                                    border-radius: 50%;
                                    width: 100px;
                                    height: 100px;
                                    object-fit: cover;
                                    display: block;
                                    margin: auto;
                                }}
                            </style>
                            <img src="data:image/png;base64,{img_base64}" class="circle-img">
                            """,
                            unsafe_allow_html=True,
                        )
                    except Exception as e:
                        st.error(f"Error loading image: {e}")
            with text_col:
                st.header(f'{st.session_state["persona"]["first_name"]} {st.session_state["persona"]["last_name"]}')
                st.subheader(st.session_state["persona"]["job_title"])
        else:
            st.info("No user selected. Please add a user.")
        st.markdown("---")
        # Load users from the database.
        db_users = get_db_users()
        if db_users:
            user_options = {
                f'{user["first_name"]} {user["last_name"]}': user for user in db_users
            }  # Map user names to user objects

            # Ensure no default selection
            st.session_state.setdefault("user_choice", None)

            selected_user = st.selectbox(
                "Select User:",
                options=["-- Select a User --"] + list(user_options.keys()),
                index=0,
                key="user_choice",
                on_change=lambda: update_persona(user_options.get(st.session_state["user_choice"], {})),
            )
        else:
            st.info("No users found. Please add a user.")

        st.button("Add User", on_click=show_add_user)
        if st.session_state.get("persona"):
            st.button("Update User", on_click=update_user)

with right_col:
    st.selectbox(
        "Select Model:",
        options=get_available_models(),
        key="selected_model",
        on_change=update_model,
    )
    st.button("Delete Chat", on_click=delete_chat, help="Clears the entire chat.")
    chat_placeholder = st.empty()
    with chat_placeholder.container():
        if st.session_state["chat_history"]:
            for i, exchange in enumerate(st.session_state["chat_history"]):
                message(
                    exchange["user"],
                    is_user=True,
                    key=f"{i}_user",
                    avatar_style="no-avatar",
                )
                if st.session_state["persona"].get("profile_photo"):
                    logo_url = image_to_base64(st.session_state["persona"]["profile_photo"])
                else:
                    logo_url = None
                message(
                    exchange["assistant"],
                    key=f"{i}",
                    allow_html=True,
                    logo=logo_url,
                    avatar_style="no-avatar",
                )
        else:
            st.write("No messages yet. Start the conversation below.")
    if st.session_state["persona"].get("id"):
        st.text_input("User Input:", key="user_input", on_change=on_text_submit)
    else:
        st.info("Chat disabled. Please add or select a user to start chatting.")
