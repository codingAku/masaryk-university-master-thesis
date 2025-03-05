import streamlit as st
import base64
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import (
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    AIMessagePromptTemplate,
    ChatPromptTemplate,
)
import db_helpers

# -----------------------------
# 3. Helper Functions for Chat
# -----------------------------
system_message = SystemMessagePromptTemplate.from_template(
    "You are {persona_name} {persona_last_name}, an employee with the job title: {persona_job}. Your native language is {native_language} and your english proficiency is {english_level}. Respond concisely like a human. Pay attention to your native language and english level, and make your answers in english like a human with the given english proficieny. Do not make the user understand you are AI. If you are prompted a question out of your specialty, reply confused. Do not generate emotions or gestures in parantheses, just write the reply."
)

def build_prompt_messages():
    persona_name = st.session_state["persona"].get("first_name", "User")
    persona_last_name = st.session_state["persona"].get("last_name", "User")
    persona_job = st.session_state["persona"].get("job_title", "N/A")
    native_language = st.session_state["persona"].get("native_language", "English")
    english_level = st.session_state["persona"].get("english_level", "C1")
    sys_msg = system_message.format(
        persona_name=persona_name,
        persona_job=persona_job,
        persona_last_name=persona_last_name,
        native_language=native_language,
        english_level=english_level
    )
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
    db_helpers.add_chat_message(person_id, "user", user_text)
    db_helpers.add_chat_message(person_id, "assistant", response_text)
    st.session_state["chat_history"] = db_helpers.get_chat_history(person_id)

def on_text_submit():
    user_text = st.session_state.get("user_input")
    process_message(user_text)
    st.session_state["input_counter"] += 1
    st.session_state["user_input"] = ""  # Clear text input

def delete_chat():
    if st.session_state["persona"].get("id"):
        db_helpers.delete_chat_history(st.session_state["persona"]["id"])
    st.session_state["chat_history"] = []

def update_model():
    st.session_state["model"] = ChatOllama(model=st.session_state["selected_model"])

def image_to_base64(image_bytes):
    return f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"
