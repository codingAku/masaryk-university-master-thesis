import streamlit as st
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
    else:
        st.session_state["chat_history"] = []


def update_user():
    st.session_state["show_add_user_form"] = True
    st.session_state["update_mode"] = True

def cancel_user_update():
    st.session_state["show_add_user_form"] = False
    st.session_state["update_mode"] = False
    st.session_state["user_choice"] = f'{st.session_state["persona"]["first_name"]} {st.session_state["persona"]["last_name"]}'

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

    transcript_data = (
        [(file.name, file.read()) for file in transcript_files]
        if transcript_files
        else []
    )
    profile_photo_bytes = profile_photo_file.read() if profile_photo_file else None
    
    if st.session_state.get("update_mode", False) and "persona" in st.session_state:
        # Update user
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
        )

        ### NEW CODE ###
        # If the user checked "Remove current profile photo?"
        if st.session_state.get("remove_profile_photo"):
            db_helpers.remove_profile_photo(st.session_state["persona"].get("id"))

        # If transcripts_to_remove is set, remove them from db_helpers
        transcripts_to_remove = st.session_state.get("transcripts_to_remove", [])
        for filename in transcripts_to_remove:
            db_helpers.remove_transcript(st.session_state["persona"].get("id"), filename)

    else:
        # Add new user
        db_helpers.add_user(
            first_name,
            last_name,
            job_title,
            native_language,
            english_level,
            personality_traits,
            profile_photo_bytes,
            transcript_data,
        )

    st.success("User saved successfully!")
    st.session_state["show_add_user_form"] = False
    st.session_state["persona"] = {}
    st.session_state["chat_history"] = []

def show_add_user():
    st.session_state["show_add_user_form"] = True
    st.session_state["update_mode"] = False
