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

# Import our indexer functions from indexer.py
from indexer import initialize_indexer, retrieve_context

# -----------------------------
# 1. Initialize Domain Indexer
# -----------------------------
def setup_rag_index():
    """
    Sets up the RAG indexer by reading domain files and saving
    the documents, FAISS index, and embedding model in st.session_state.
    """
    domain_files = [
        "stakeholder-info/Toucan-GLOS.txt",
        "stakeholder-info/Full-MVR.txt",
        "stakeholder-info/manufacturing-flow.txt",
        "stakeholder-info/MVR-rules-revision.txt"
    ]
    
    if "rag_index" not in st.session_state:
        documents, index, embedding_model = initialize_indexer(domain_files)
        st.session_state["rag_documents"] = documents
        st.session_state["rag_index"] = index
        st.session_state["rag_embedding_model"] = embedding_model

# -----------------------------
# 2. Chat Helper Functions
# -----------------------------
def initialize_persona_session():
    """
    Initializes the session for the selected persona by creating a detailed system prompt.
    The prompt includes persona details and transcript excerpts for context.
    """
    persona = st.session_state["persona"]
    transcripts = persona.get("transcripts", [])
    transcripts_text = "\n".join([
            t.get("file_content", b"").decode("utf-8", errors="ignore") if isinstance(t.get("file_content", b""), bytes)
            else t.get("file_content", str(t))
            for t in transcripts
        ]) if transcripts else "No transcripts available."
    
    system_prompt = (
        f"You are {persona.get('first_name', 'User')} {persona.get('last_name', 'User')}, an employee with the job title: {persona.get('job_title', 'N/A')}. You may look in this prompt for your job description. "
        "You work at Thermo Fisher Scientific. You are stakeholder to an application named Toucan, used for manufacturing of optical emission and xr spectrometers. You will talk requirement elicitation with your software developer co-worker in this session."
        f"Your native language is {persona.get('native_language', 'English')}, but the conversations will be in English. and your English proficiency is {persona.get('english_level', 'C1')}."
        "Therefore your english level will be crucial in the conversation. Respond in the given level. If your english level is relatively low, you can use some words in your native language from time to time."
        "Respond concisely like a human. Do not generate emotions or reactions, just generate the human answer. Do not include your thought process, just return the answer you give to the user. Do not explain your thought flow as an AI model, only return in the prompt the answer during conversation. Pay attention to your native language and English level, and craft your replies accordingly. "
        "Do not reveal that you are AI. If asked about topics outside your area of expertise, reply with confusion."
        "Avoid generating emotions or gestures in parentheses; simply provide your reply.\n\n"
        "The following transcript excerpts from previous meetings provide additional context for your persona. In the transcript, look for the answers of the person you are by name. You must pay attention to the information and also the way of speaking for the person, you can use the information in the transcripts and answer like the persona:\n"
        f"{transcripts_text}\n\n"
        "You can observe how the human you impersonate talks in the transcript by looking at sentences with your persona name. And then you can reply similar to how that person does. "
        "Please use this context along with any previous conversation history to ensure your responses remain consistent with your persona."
    )
    
    st.session_state["persona_system_prompt"] = system_prompt

def build_prompt_messages():
    """
    Builds the chat prompt messages by starting with the persona-specific system prompt
    and then appending the chat history to maintain context.
    """
    sys_msg_template = SystemMessagePromptTemplate.from_template(
        st.session_state["persona_system_prompt"]
    )
    prompt_msgs = [sys_msg_template]
    
    # Append conversation history for context.
    for entry in st.session_state["chat_history"]:
        prompt_msgs.append(HumanMessagePromptTemplate.from_template(entry["user"]))
        prompt_msgs.append(AIMessagePromptTemplate.from_template(entry["assistant"]))
    return ChatPromptTemplate.from_messages(prompt_msgs)

def generate_response(user_text):
    # Ensure the RAG index is set up.
    setup_rag_index()
    
    # Retrieve domain context using the RAG indexer based on the user query.
    domain_context = retrieve_context(
        user_text,
        st.session_state["rag_documents"],
        st.session_state["rag_index"],
        st.session_state["rag_embedding_model"],
        top_k=3
    )
    
    # Create a system message with the retrieved domain context.
    domain_sys_prompt = SystemMessagePromptTemplate.from_template(
        f"Use the following domain context to help answer the query:\n\n{domain_context}"
    )
    
    # Build the prompt messages: start with domain context, then persona prompt and chat history.
    persona_sys_prompt = SystemMessagePromptTemplate.from_template(
        st.session_state["persona_system_prompt"]
    )
    
    messages = [domain_sys_prompt, persona_sys_prompt]
    for entry in st.session_state["chat_history"]:
        messages.append(HumanMessagePromptTemplate.from_template(entry["user"]))
        messages.append(AIMessagePromptTemplate.from_template(entry["assistant"]))
    
    messages.append(HumanMessagePromptTemplate.from_template(user_text))
    
    chat_prompt = ChatPromptTemplate.from_messages(messages)
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
    db_helpers.add_chat_message(person_id, "user", user_text)
    db_helpers.add_chat_message(person_id, "assistant", response_text)
    st.session_state["chat_history"] = db_helpers.get_chat_history(person_id)

def on_text_submit():
    user_text = st.session_state.get("user_input")
    process_message(user_text)
    st.session_state["input_counter"] += 1
    st.session_state["user_input"] = ""

def delete_chat():
    if st.session_state["persona"].get("id"):
        db_helpers.delete_chat_history(st.session_state["persona"]["id"])
    st.session_state["chat_history"] = []

def update_model():
    st.session_state["model"] = ChatOllama(model=st.session_state["selected_model"])

def image_to_base64(image_bytes):
    return f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"
