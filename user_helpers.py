import streamlit as st
import chat_helpers
import db_helpers

# -----------------------------
# 4. Database Helper Functions for Users
# -----------------------------
def get_db_users():
    return db_helpers.get_users()

def update_persona(new_persona):
    st.session_state["persona"] = new_persona
    if new_persona.get("id"):
        st.session_state["chat_history"] = db_helpers.get_chat_history(new_persona["id"])
        # Also fetch transcripts and store in persona
        st.session_state["persona"]["transcripts"] = db_helpers.get_user_transcripts(new_persona["id"])
        # Fetch and store audio files for the user
        st.session_state["persona"]["audios"] = db_helpers.get_user_audios(new_persona["id"])
    else:
        st.session_state["chat_history"] = []
    chat_helpers.initialize_persona_session()

def update_user():
    # Backup the current persona so we can restore if cancelled
    if st.session_state.get("persona"):
        st.session_state["backup_persona"] = st.session_state["persona"].copy()
    st.session_state["show_add_user_form"] = True
    st.session_state["update_mode"] = True
    # Note: For update, we do NOT clear the persona so the form remains pre-filled.

def show_add_user():
    # Backup the current persona if one is selected
    if st.session_state.get("persona"):
        st.session_state["backup_persona"] = st.session_state["persona"].copy()
    st.session_state["show_add_user_form"] = True
    st.session_state["update_mode"] = False
    # Clear the persona to start with a blank form for a new user
    st.session_state["persona"] = {}

def cancel_user_update():
    st.session_state["show_add_user_form"] = False
    st.session_state["update_mode"] = False
    if "backup_persona" in st.session_state:
        # Restore the backed-up persona and update the dropdown accordingly
        st.session_state["persona"] = st.session_state["backup_persona"]
        full_name = f'{st.session_state["persona"].get("first_name", "")} {st.session_state["persona"].get("last_name", "")}'.strip()
        st.session_state["user_choice"] = full_name if full_name else "-- Select a User --"
        del st.session_state["backup_persona"]
    # If there's no backup, do not change the dropdown

def delete_user():
    if st.session_state["persona"].get("id"):
        db_helpers.delete_chat_history(st.session_state["persona"]["id"])
        db_helpers.delete_user(st.session_state["persona"]["id"])
    st.session_state["persona"] = {}
    st.session_state["chat_history"] = []
    st.session_state["show_add_user_form"] = False

def submit_new_user():
    first_name = st.session_state.get("first_name", "")
    last_name = st.session_state.get("last_name", "")
    job_title = st.session_state.get("job_title", "")
    native_language = st.session_state.get("native_language", "")
    english_level = st.session_state.get("english_level", "")
    personality_traits = st.session_state.get("personality_traits", "")
    profile_photo_file = st.session_state.get("profile_photo")
    transcript_files = st.session_state.get("transcript_files", [])
    audio_file = st.session_state.get("audio_files")  # Single file expected

    transcript_data = (
        [(file.name, file.read()) for file in transcript_files]
        if transcript_files
        else []
    )
    audio_data = [(audio_file.name, audio_file.read())] if audio_file else []
    profile_photo_bytes = profile_photo_file.read() if profile_photo_file else None

    if st.session_state.get("update_mode", False) and "persona" in st.session_state:
        # Update user, now including audio_data
        db_helpers.update_user(
            st.session_state["persona"].get("id"),
            first_name,
            last_name,
            job_title,
            native_language,
            english_level,
            personality_traits,
            profile_photo_bytes,
            transcript_data,
            audio_data
        )

        # If the user checked "Remove current profile photo?"
        if st.session_state.get("remove_profile_photo"):
            db_helpers.remove_profile_photo(st.session_state["persona"].get("id"))

        # If transcripts_to_remove is set, remove them from db_helpers
        transcripts_to_remove = st.session_state.get("transcripts_to_remove", [])
        for filename in transcripts_to_remove:
            db_helpers.remove_transcript(st.session_state["persona"].get("id"), filename)
        
        # If the user checked "Remove the audio file"
        if st.session_state.get("remove_audio_file"):
            audios = st.session_state["persona"].get("audios", [])
            if audios:
                # Assuming only one audio file exists, remove the first one.
                filename = audios[0].get("filename")
                if filename:
                    db_helpers.remove_audio(st.session_state["persona"].get("id"), filename)
    else:
        # Add new user, now including audio_data
        db_helpers.add_user(
            first_name,
            last_name,
            job_title,
            native_language,
            english_level,
            personality_traits,
            profile_photo_bytes,
            transcript_data,
            audio_data
        )

    st.success("User saved successfully!")
    st.session_state["show_add_user_form"] = False
    st.session_state["persona"] = {}
    st.session_state["chat_history"] = []
