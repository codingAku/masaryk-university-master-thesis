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
import time # For potential debugging/waiting

# Import our indexer functions from indexer.py
from indexer import initialize_indexer, retrieve_context

# NEW IMPORT: Import tokenizer's chunk_text method.
from tokenizer import chunk_text

# --- Constants ---
TTS_URL = "http://localhost:58004/tts" # Define URL once

# -----------------------------
# 1. Initialize Domain Indexer
# (Keep this section as is)
# -----------------------------
@st.cache_resource
def get_cached_index():
    domain_files = [
        "stakeholder-info/Toucan-GLOS.txt",
        "stakeholder-info/Full-MVR.txt",
        "stakeholder-info/manufacturing-flow.txt",
        "stakeholder-info/MVR-rules-revision.txt",
        "stakeholder-info/job-description.txt",
        "stakeholder-info/ticket-description.txt",
        "stakeholder-info/toucan-description.txt",
    ]
    # Ensure files exist or handle gracefully
    existing_files = [f for f in domain_files if os.path.exists(f)]
    if len(existing_files) != len(domain_files):
        st.warning(f"Missing some domain files. Found: {existing_files}")
    if not existing_files:
        st.error("No domain files found for RAG index!")
        return None, None, None # Or raise an error
    return initialize_indexer(existing_files)

def setup_rag_index():
    if "rag_index" not in st.session_state:
        # Add check in case get_cached_index returns None
        result = get_cached_index()
        if result and all(item is not None for item in result):
             documents, index, embedding_model = result
             st.session_state["rag_documents"] = documents
             st.session_state["rag_index"] = index
             st.session_state["rag_embedding_model"] = embedding_model
        else:
            st.error("Failed to initialize RAG index. Check domain files.")
            # Disable features requiring RAG or handle appropriately
            st.session_state["rag_index"] = None # Indicate failure


# -----------------------------
# 2. Chat Helper Functions
# (Keep initialize_persona_session, build_prompt_messages, generate_response as is,
#  but ensure setup_rag_index is called robustly in generate_response)
# -----------------------------

# --- Modify process_message ---
def generate_response(user_text):
    """
    Generates a response from the LLM using RAG context.
    """
    # Ensure the RAG index is set up. Handles potential setup failures.
    setup_rag_index()
    if "rag_index" not in st.session_state or st.session_state["rag_index"] is None:
         st.error("RAG index not initialized. Cannot retrieve context.")
         # Return a default message or raise an error, depending on desired behavior
         return "Sorry, I cannot process your request right now due to an internal setup issue."

    # Retrieve domain context using the RAG indexer.
    # Add error handling for retrieval if necessary
    try:
        domain_context = retrieve_context(
            user_text,
            st.session_state["rag_documents"],
            st.session_state["rag_index"],
            st.session_state["rag_embedding_model"],
            top_k=3
        )
    except Exception as e:
        st.warning(f"Failed to retrieve RAG context: {e}")
        domain_context = "No specific context could be retrieved." # Provide fallback context

    # Create a system message with the retrieved domain context.
    domain_sys_prompt = SystemMessagePromptTemplate.from_template(
        f"Use the following domain context to help answer the query:\n\n{domain_context}"
    )

    # Build the prompt messages including persona and history.
    # Ensure persona system prompt exists
    if "persona_system_prompt" not in st.session_state:
        st.error("Persona prompt not initialized.")
        return "Sorry, I cannot process your request right now. Persona not set up."

    persona_sys_prompt = SystemMessagePromptTemplate.from_template(
        st.session_state["persona_system_prompt"]
    )

    messages = [domain_sys_prompt, persona_sys_prompt]
    # Ensure chat history exists and is a list
    chat_history = st.session_state.get("chat_history", [])
    if not isinstance(chat_history, list):
        st.warning("Chat history format is invalid. Resetting.")
        chat_history = []
        st.session_state["chat_history"] = []

    for entry in chat_history:
        # Add validation for entry format if needed
        if isinstance(entry, dict) and "user" in entry and "assistant" in entry:
            messages.append(HumanMessagePromptTemplate.from_template(entry["user"]))
            messages.append(AIMessagePromptTemplate.from_template(entry["assistant"]))
        else:
            st.warning(f"Skipping invalid chat history entry: {entry}")


    messages.append(HumanMessagePromptTemplate.from_template(user_text))

    # Ensure the model is initialized
    if "model" not in st.session_state or st.session_state["model"] is None:
        st.error("LLM model is not initialized.")
        return "Sorry, the language model is not available."

    chat_prompt = ChatPromptTemplate.from_messages(messages)
    chain = chat_prompt | st.session_state["model"] | StrOutputParser()

    # Add error handling for the LLM call
    try:
        response = chain.invoke({})
    except Exception as e:
        st.error(f"Error invoking the language model: {e}")
        response = "Sorry, I encountered an error trying to generate a response."

    return response
def process_message(user_text):
    if not user_text.strip():
        st.warning("Please enter a message before sending.")
        return
    if "persona" not in st.session_state or not st.session_state["persona"].get("id"):
        st.warning("No user selected or persona not initialized. Please add or select a user.")
        return
    if "rag_index" not in st.session_state or st.session_state["rag_index"] is None:
        st.error("RAG index not available. Cannot generate response.")
        return

    try:
        response_text = generate_response(user_text)
    except Exception as e:
        st.error(f"Error generating response: {e}")
        return # Stop processing if LLM fails

    person_id = st.session_state["persona"]["id"]
    db_helpers.add_chat_message(person_id, "user", user_text)
    db_helpers.add_chat_message(person_id, "assistant", response_text)
    st.session_state["chat_history"] = db_helpers.get_chat_history(person_id) # Refresh history *before* potential thread issues

    # --- Voice Generation Integration ---
    if st.session_state.get("enable_voice_generation") and "deepseek-r1" not in st.session_state.get("selected_model", "").lower():
        # **CRITICAL CHANGE 1: Get persona data BEFORE starting the thread**
        # Pass a copy to avoid potential modification issues if the main thread changes it
        # while the background thread is running (less likely here, but good practice).
        persona_data_for_thread = st.session_state["persona"].copy()

        # Create a placeholder to store the result from the thread
        audio_result_container = {"audio_bytes_list": None, "error": None}

        # Define the target function for the thread
        def thread_target(text, persona_data, result_container):
            try:
                # Call the function that does the work, passing the explicit data
                audio_bytes = generate_audio_bytes(text, persona_data)
                result_container["audio_bytes_list"] = audio_bytes
            except Exception as e:
                # Store the error to potentially show it in the main thread
                result_container["error"] = f"Error in audio generation thread: {e}"
                print(f"Error in audio generation thread: {e}") # Also log it


        # Start the thread, passing the necessary data
        audio_thread = Thread(
            target=thread_target,
            args=(response_text, persona_data_for_thread, audio_result_container),
            # Add daemon=True if you want the thread to exit automatically when the main program exits
            # daemon=True
        )
        audio_thread.start()

        # **CRITICAL CHANGE 2: Handle the result IN THE MAIN THREAD**
        # You *cannot* call Streamlit UI functions (like st.components.v1.html)
        # from the background thread. You must get the result back to the main thread.

        # Option A: Wait for the thread to finish (blocks the UI during wait)
        audio_thread.join() # Wait here until the thread completes

        # Check if the thread produced audio or an error
        if audio_result_container["error"]:
            st.error(audio_result_container["error"])
        elif audio_result_container["audio_bytes_list"]:
            # Call the playback function from the main thread
            play_audio_sequence(audio_result_container["audio_bytes_list"])

        # Option B: (More Advanced) Use st.rerun periodically to check if the thread
        # is done without blocking. This requires storing the thread object and result
        # container in session state and checking `audio_thread.is_alive()` on reruns.
        # This is more complex to manage state correctly. Sticking with Option A for now.


# **CRITICAL CHANGE 3: Modify generate_and_play_audio**
# Rename it and make it RETURN the audio data, not play it directly.
# Also accept persona data as an argument.
def generate_audio_bytes(response_text, persona_data):
    """
    Generates audio bytes for the response text using TTS.
    Accepts persona data explicitly.
    Returns a list of audio byte chunks.
    """
    chunks = chunk_text(response_text) # Assuming chunk_text is available
    user_audio_file = None # This variable wasn't used in send_to_tts anyway based on your code

    # Get the required 'first_name' from the passed persona_data
    first_name = persona_data.get("first_name")
    if not first_name:
        # Handle case where first_name might be missing in the persona data
        print("Warning: 'first_name' missing in persona_data for TTS speaker ref.")
        # Decide on fallback behavior: maybe use a default speaker, or skip TTS for this chunk/response
        # For now, let's return empty list to indicate failure
        return []

    audio_chunks_bytes = []
    for chunk in chunks:
        audio_data = send_to_tts(chunk, first_name) # Pass only needed data
        if audio_data:
            audio_chunks_bytes.append(audio_data)
        else:
            # Log or handle failed TTS for a specific chunk if needed
            print(f"Warning: Failed to get TTS for chunk: '{chunk[:30]}...'")

    return audio_chunks_bytes


# --- Keep other functions like on_text_submit, delete_chat, update_model, image_to_base64 ---
def on_text_submit():
    user_text = st.session_state.get("user_input")
    # Add input validation if needed here before calling process_message
    process_message(user_text)
    # It's generally better practice to clear the input *after* successful processing
    # or based on the outcome of process_message, but this works for now.
    # Check if 'input_counter' exists before incrementing
    if "input_counter" not in st.session_state:
        st.session_state["input_counter"] = 0
    st.session_state["input_counter"] += 1
    st.session_state["user_input"] = "" # Clear the input field


def delete_chat():
    # Ensure 'persona' exists before trying to access its 'id'
    if "persona" in st.session_state and st.session_state["persona"].get("id"):
        db_helpers.delete_chat_history(st.session_state["persona"]["id"])
    st.session_state["chat_history"] = [] # Always clear local history


def update_model():
    selected_model = st.session_state.get("selected_model")
    if selected_model:
        try:
            st.session_state["model"] = ChatOllama(model=selected_model)
            # If a deepseek model is selected, ensure voice generation is disabled.
            if "deepseek-r1" in selected_model.lower():
                st.session_state["enable_voice_generation"] = False
        except Exception as e:
            st.error(f"Failed to initialize model '{selected_model}': {e}")
            # Optionally reset to a default model or disable chat
            st.session_state["model"] = None
    else:
        st.warning("No model selected.")
        st.session_state["model"] = None


def image_to_base64(image_bytes):
    if not isinstance(image_bytes, bytes):
        # Handle cases where input might not be bytes (e.g., None or already encoded)
        st.error("Invalid input for image_to_base64: Expected bytes.")
        return None # Or raise error
    try:
        return f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"
    except Exception as e:
        st.error(f"Error encoding image to base64: {e}")
        return None

# --- Modify send_to_tts ---
def send_to_tts(text_chunk, first_name):
    """
    Sends a TTS request using the provided text chunk and first_name for speaker ref.
    Returns the audio data (wav file bytes) or None on failure.
    """
    # Use the constant URL
    url = TTS_URL
    # Prepare the payload with text and the required speaker reference path.
    # Ensure first_name is valid for a filename if needed, or handle variations.
    speaker_ref = f"assets/{first_name}.mp3" # Assuming this path format is correct for the TTS service

    # Check if the reference file actually exists (optional but good for debugging)
    # if not os.path.exists(speaker_ref):
    #     st.warning(f"Speaker reference file not found: {speaker_ref}")
        # Decide if you want to proceed with a default or fail
        # return None # Example: fail if ref file missing

    data = {"text": text_chunk, "speaker_ref_path": speaker_ref}

    try:
        # Add a timeout to prevent indefinite hangs
        response = requests.post(url, data=data, timeout=30) # 30 second timeout
        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        # Check content type if possible, though often TTS returns raw bytes
        # if 'audio/wav' in response.headers.get('Content-Type', ''):
        return response.content # This is the wav file bytes.
        # else:
        #     st.error(f"TTS service returned unexpected content type: {response.headers.get('Content-Type')}")
        #     return None
    except requests.exceptions.RequestException as e:
        # Handle specific request errors (ConnectionError, Timeout, HTTPError, etc.)
        st.error(f"TTS request failed: {e}")
        print(f"TTS request failed for url {url} with data {data}: {e}") # Log more details
        return None
    except Exception as e:
        # Catch other unexpected errors
        st.error(f"An unexpected error occurred during TTS request: {e}")
        print(f"Unexpected error during TTS for url {url} with data {data}: {e}")
        return None


# --- Modify play_audio_sequence ---
# It now accepts a list of audio byte chunks
def play_audio_sequence(audio_bytes_list):
    """
    Plays the provided audio byte chunks sequentially in the browser.
    This function MUST be called from the main Streamlit thread.
    """
    if not audio_bytes_list:
        print("No valid audio chunks to play.")
        return

    # Convert each audio chunk (bytes) to a base64 data URL.
    audio_data_urls = []
    for i, chunk_bytes in enumerate(audio_bytes_list):
        try:
            b64_audio = base64.b64encode(chunk_bytes).decode()
            data_url = f"data:audio/wav;base64,{b64_audio}"
            audio_data_urls.append(data_url)
        except Exception as e:
            st.error(f"Failed to encode audio chunk {i+1} to base64: {e}")
            # Skip this chunk or stop playback? For now, skip.

    if not audio_data_urls:
        st.warning("No audio chunks could be successfully encoded for playback.")
        return

    # Build a JavaScript snippet that plays the audio URLs sequentially.
    # Ensure the list is correctly formatted as a JS array literal.
    import json
    js_code = f"""
    <script>
        const audioUrls = {json.dumps(audio_data_urls)}; // Use json.dumps for safety
        let currentAudioIndex = 0;
        const audioPlayer = new Audio();

        function playNext() {{
            if (currentAudioIndex < audioUrls.length) {{
                console.log("Playing audio chunk:", currentAudioIndex + 1, "/", audioUrls.length);
                audioPlayer.src = audioUrls[currentAudioIndex];
                // Use a promise to handle potential play errors
                var playPromise = audioPlayer.play();
                if (playPromise !== undefined) {{
                    playPromise.then(_ => {{
                        // Automatic playback started!
                    }})
                    .catch(error => {{
                        // Auto-play was prevented, maybe log or inform user
                        console.error("Audio playback failed for chunk " + (currentAudioIndex + 1) + ":", error);
                        // Attempt to play next chunk even if one fails? Or stop?
                        // Let's try moving to the next one via the 'ended' event anyway
                        // or maybe trigger the ended event manually after a short delay
                        // setTimeout(handleAudioEnd, 100); // Or just rely on 'ended' listener
                    }});
                }}
            }} else {{
                console.log("Finished playing all audio chunks.");
            }}
        }}

        function handleAudioEnd() {{
            console.log("Audio chunk ended:", currentAudioIndex + 1);
            currentAudioIndex++;
            playNext(); // Play the next chunk
        }}

        // Remove previous listeners if any (safer if this runs multiple times)
        // This is tricky without managing the player instance more globally,
        // but for a simple sequential play, adding might be okay, or risk multiple plays.
        // A better approach might involve a unique ID for the script/player.
        audioPlayer.removeEventListener('ended', handleAudioEnd); // Try removing first
        audioPlayer.addEventListener('ended', handleAudioEnd);

        // Start playing the first chunk
        playNext();

    </script>
    """
    # Inject the JavaScript into the Streamlit app.
    st.components.v1.html(js_code, height=0, width=0)