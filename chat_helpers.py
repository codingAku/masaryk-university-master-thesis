from threading import Thread
import streamlit as st
import os
import base64
import requests
from langchain_ollama import ChatOllama
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import (
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    AIMessagePromptTemplate,
    ChatPromptTemplate,
)
import db_helpers

from indexer import initialize_indexer, retrieve_context
from tokenizer import chunk_text, remove_parentheses

URL = "http://host.docker.internal:58004/tts"
# -----------------------------
# 1. Initialize Domain Indexer
# -----------------------------
@st.cache_resource
def get_cached_index():
    domain_files = [
        "stakeholder-info/Toucan-Glossary.txt",
        f"stakeholder-info/Full-MVR-{st.session_state['persona']['first_name']}.txt",
        f"stakeholder-info/Manufacturing-Flow-{st.session_state['persona']['first_name']}.txt",
        f"stakeholder-info/MVR-Curve-Rules-{st.session_state['persona']['first_name']}.txt",
        "stakeholder-info/Role-Descriptions.txt",
        "stakeholder-info/Toucan-Description.txt",
    ]

    return initialize_indexer(domain_files)


def setup_rag_index():
    if "rag_index" not in st.session_state:
        documents, index, embedding_model = get_cached_index()
        st.session_state["rag_documents"] = documents
        st.session_state["rag_index"] = index
        st.session_state["rag_embedding_model"] = embedding_model

# -----------------------------
# 2. Chat Helper Functions
# -----------------------------
def initialize_persona_session():
    """
    Initializes the session for the selected persona by creating a detailed system prompt.
    """
    persona = st.session_state["persona"]
    transcripts = persona.get("transcripts", [])
    transcripts_text = "\n".join([
            t.get("file_content", b"").decode("utf-8", errors="ignore") if isinstance(t.get("file_content", b""), bytes)
            else t.get("file_content", str(t))
            for t in transcripts
        ]) if transcripts else "No transcripts available."
    
    ticket_path = f"stakeholder-info/Jira-Ticket-{persona.get('first_name')}.txt"
    ticket_description = ""
    if os.path.exists(ticket_path):
        with open(ticket_path, "r", encoding="utf-8") as f:
            ticket_description = f.read()
    
    system_prompt = (
        f"You are {persona.get('first_name', 'User')} {persona.get('last_name', 'User')}, an employee with the job title: {persona.get('job_title', 'N/A')}. You may look in this prompt for your job description. "
        "You work at Thermo Fisher Scientific. You are stakeholder to an application named Toucan, used for manufacturing of optical emission and xr spectrometers. You will talk about a ticket with your software developer co-worker in this session, to tell your problem to them."
        f"Here is ticket description: {ticket_description}"
        f"Your native language is {persona.get('native_language', 'English')}, but the conversations will be in English. and your English proficiency is {persona.get('english_level', 'C1')}."
        "Therefore your english level will be crucial in the conversation. Respond in the given level. If your english level is relatively low, you can use some words in your native language from time to time."
        "Respond concisely like a human. Do not generate emotions or reactions in parantheses, just generate the human answer. Do not include your thought process, just return the answer you give to the user. Do not explain your thought flow as an AI model, only return in the prompt the answer during conversation. Pay attention to your native language and English level, and craft your replies accordingly. "
        "Do not reveal that you are AI. If asked about topics outside your area of expertise, reply with confusion. Be a bit aggresive against code questions."
        f"Use the transcript where you can find stakeholder style of talking. Mimic it. Do not use information in the meeting, only look at the way they talk. In the transcript, look for the answers of the person you are by name. Answer like the persona: {transcripts_text}"
        "Please use this context along with any previous conversation history to ensure your responses remain consistent with your persona."
    )
    
    st.session_state["persona_system_prompt"] = system_prompt


def generate_response(user_text):
    # Ensure the RAG index is set up.
    setup_rag_index()
    
    # Retrieve domain context using the RAG indexer.
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
    
    # Build the prompt messages.
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
    response_text = remove_parentheses(generate_response(user_text))
    person_id = st.session_state["persona"]["id"]
    db_helpers.add_chat_message(person_id, "user", user_text)
    db_helpers.add_chat_message(person_id, "assistant", response_text)
    st.session_state["chat_history"] = db_helpers.get_chat_history(person_id)
    
    # --- Voice Generation Integration ---
    # Only proceed if voice generation is enabled and the selected model is not deepseek.
    if st.session_state.get("enable_voice_generation") and "deepseek-r1" not in st.session_state.get("selected_model", "").lower():
       # Tokenize the generated response text.
        chunks = chunk_text(response_text)
        audio_chunks = []
        # Retrieve user's sound file if available; assume the first audio file.
        user_audio_file = None
        if st.session_state["persona"].get("audios"):
            user_audio_file = st.session_state["persona"]["audios"][0].get("file_content")
        for chunk in chunks:
            # Send TTS request to metavoice TTS service with chunk text and user_audio_file.
            audio_data = send_to_tts(chunk, user_audio_file)
            audio_chunks.append(audio_data)
        play_audio_sequence(audio_chunks)

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
    # If a deepseek model is selected, ensure voice generation is disabled.
    if "deepseek-r1" in st.session_state["selected_model"].lower():
        st.session_state["enable_voice_generation"] = False

def image_to_base64(image_bytes):
    return f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"

# --- New Helper Functions for Voice TTS Integration ---

def send_to_tts(text_chunk, user_audio_file):
    """
    Sends a TTS request to the metavoice TTS service using the provided text chunk
    and the user's audio file (if available). Returns the audio data (wav file bytes).
    """
    url = URL
    # Prepare the payload with text.
    data = {"text": text_chunk,  "speaker_ref_path": f"assets/{st.session_state["persona"]["first_name"]}.mp3"}
    # files = None
    # # If a user audio file is provided, send it as 'audiodata'
    # if user_audio_file:
    #     files = {
    #         "speaker_ref_path": ("assets/slyvain.mp3")
    #     }
    try:
        response = requests.post(url, data=data)
        response.raise_for_status()
        return response.content  # This is the wav file bytes.
    except Exception as e:
        st.error(f"TTS request failed: {e}")
        return None

def play_audio_sequence(audio_chunks):
    """
    Plays the provided audio chunks sequentially in the browser using injected JavaScript.
    The audio chunks are base64 encoded and chained for sequential playback.
    """
    # Filter out any None values.
    valid_chunks = [chunk for chunk in audio_chunks if chunk]
    if not valid_chunks:
        return

    # Convert each audio chunk to a base64 data URL.
    audio_data_urls = []
    for chunk in valid_chunks:
        b64_audio = base64.b64encode(chunk).decode()
        data_url = f"data:audio/wav;base64,{b64_audio}"
        audio_data_urls.append(data_url)

    # Build a JavaScript snippet that plays the audio URLs sequentially.
    js_code = f"""
    <script>
    const audioUrls = {audio_data_urls};
    let current = 0;
    const audioPlayer = new Audio();
    audioPlayer.src = audioUrls[current];
    audioPlayer.play();
    audioPlayer.addEventListener('ended', () => {{
        current++;
        if (current < audioUrls.length) {{
            audioPlayer.src = audioUrls[current];
            audioPlayer.play();
        }}
    }});
    </script>
    """
    # Inject the JavaScript into the Streamlit app.
    st.components.v1.html(js_code, height=0, width=0)
