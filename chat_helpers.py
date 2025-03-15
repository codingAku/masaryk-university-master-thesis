import streamlit as st
import os
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
def initialize_persona_session():
    """
    Initializes the session for the selected persona by creating a detailed system prompt.
    The prompt includes persona details (name, job title, native language, English level) and
    transcript excerpts for context.
    """
    persona = st.session_state["persona"]
    transcripts = persona.get("transcripts", [])
    transcripts_text = "\n".join([
            t.get("file_content", b"").decode("utf-8", errors="ignore") if isinstance(t.get("file_content", b""), bytes)
            else t.get("file_content", str(t))
            for t in transcripts
        ]) if transcripts else "No transcripts available."
    
    stakeholder_info = load_system_prompts_from_directory("stakeholder-info")
    
    system_prompt = (
        f"You are {persona.get('first_name', 'User')} {persona.get('last_name', 'User')}, an employee with the job title: {persona.get('job_title', 'N/A')}. You may look in this prompt for your job description. "
        "You work at Thermo Fisher Scientific. You are stakeholder to an application named Toucan, used for manufacturing of optical emission and xr spectrometers. You will talk requirement elicitation with your software developer co-worker in this session."
        f"Your native language is {persona.get('native_language', 'English')}, but the conversations will be in English. and your English proficiency is {persona.get('english_level', 'C1')}."
        "Therefore your english level will be crucial in the conversation. Respond in the given level."
        "Respond concisely like a human. Do not include your thought process, just return the answer you give to the user. Do not explain your thought flow as an AI model, only return in the prompt the answer during conversation. Pay attention to your native language and English level, and craft your replies accordingly. "
        "Do not reveal that you are AI. If asked about topics outside your area of expertise, reply with confusion."
        "Avoid generating emotions or gestures in parentheses; simply provide your reply.\n\n"
        "The following transcript excerpts from previous meetings provide additional context for your persona. In the transcript, look for the answers of the person you are by name. You must pay attention to the information and also the way of speaking for the person, you can use information in the transcipts and answer like the persona:\n"
        f"{transcripts_text}\n\n"
        "You can observe how the human you impersonate talks in the transcript by looking at sentences with your persona name. And then you can reply similar to how that person does."
        "Please use this context along with any previous conversation history to ensure your responses remain consistent with your persona."
        # "Here are some domain information for you to use:"
        # f"{stakeholder_info}"
    )
    
    # Store the full system prompt in the session state
    st.session_state["persona_system_prompt"] = system_prompt

def load_system_prompts_from_directory(directory_path):
    """
    Reads all text files in the given directory and concatenates their contents as the system prompt.
    """
    system_prompts = []
    for filename in os.listdir(directory_path):
        file_path = os.path.join(directory_path, filename)
        if os.path.isfile(file_path) and filename.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as file:
                system_prompts.append(file.read())
    
    return "\n\n".join(system_prompts)
        



def build_prompt_messages():
    """
    Builds the chat prompt messages by starting with the persona-specific system prompt (if available)
    and then appending the chat history. This ensures the model uses the persona context and transcripts.
    """
    # Use the persona-specific system prompt if available; otherwise, fall back to the default system message.
    if "persona_system_prompt" in st.session_state and st.session_state["persona_system_prompt"]:
        
        sys_msg_template = SystemMessagePromptTemplate.from_template(
            st.session_state["persona_system_prompt"]
        )
    prompt_msgs = [sys_msg_template]
    
    # Append the conversation history (chat_history) to maintain context.
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
