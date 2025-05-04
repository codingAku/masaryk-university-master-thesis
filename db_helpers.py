# Copyright (c) 2025, Ecenur Sezer
# Licensed under the BSD 3-Clause License
# See the LICENSE file in the project root for full license text.

import os
from sqlalchemy import create_engine, Column, Integer, String, LargeBinary, Text, ForeignKey, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship

# Get the database URL from the environment (set in Docker Compose)
DATABASE_URL = os.environ.get("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Person(Base):
    __tablename__ = "person"
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    job_title = Column(String)
    native_language = Column(String)
    english_level = Column(String)
    personality_traits = Column(Text)
    profile_photo = Column(LargeBinary)
    transcript_files = relationship("Transcript", back_populates="person", cascade="all, delete-orphan")
    audio_files = relationship("Audio", back_populates="person", cascade="all, delete-orphan")
    chat_history = relationship("ChatHistory", back_populates="person", cascade="all, delete-orphan")

class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("person.id"), nullable=False)
    role = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    person = relationship("Person", back_populates="chat_history")

class Transcript(Base):
    __tablename__ = "transcript"
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("person.id"), nullable=False)
    file_name = Column(String, nullable=False)
    file_content = Column(LargeBinary, nullable=False)
    
    person = relationship("Person", back_populates="transcript_files")

class Audio(Base):
    __tablename__ = "audio"
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("person.id"), nullable=False)
    file_name = Column(String, nullable=False)
    file_content = Column(LargeBinary, nullable=False)
    
    person = relationship("Person", back_populates="audio_files")

def init_db():
    Base.metadata.create_all(bind=engine)

def add_user(first_name, last_name, job_title, native_language, english_level, personality_traits, profile_photo_bytes, transcript_files, audio_files):
    db = SessionLocal()
    new_person = Person(
        first_name=first_name,
        last_name=last_name,
        job_title=job_title,
        native_language=native_language,
        english_level=english_level,
        personality_traits=personality_traits,
        profile_photo=profile_photo_bytes,
    )
    db.add(new_person)
    db.commit()
    db.refresh(new_person)
    
    # Save transcript files
    for file_name, file_content in transcript_files:
        transcript = Transcript(person_id=new_person.id, file_name=file_name, file_content=file_content)
        db.add(transcript)
    
    # Save audio files
    for file_name, file_content in audio_files:
        audio = Audio(person_id=new_person.id, file_name=file_name, file_content=file_content)
        db.add(audio)
    
    db.commit()
    db.close()
    return new_person

def get_users():
    db = SessionLocal()
    users = db.query(Person).all()
    db.close()
    return [
        {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "job_title": user.job_title,
            "profile_photo": user.profile_photo,
            "native_language": user.native_language,
            "english_level": user.english_level,
            "personality_traits": user.personality_traits,
        }
        for user in users
    ]

def add_chat_message(person_id, role, message):
    db = SessionLocal()
    chat = ChatHistory(person_id=person_id, role=role, message=message)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    db.close()
    return chat

def get_chat_history(person_id):
    db = SessionLocal()
    history = db.query(ChatHistory).filter(ChatHistory.person_id == person_id).order_by(ChatHistory.timestamp).all()
    db.close()
    exchanges = []
    current_exchange = {}
    for h in history:
        if h.role == "user":
            if current_exchange:
                exchanges.append(current_exchange)
            current_exchange = {"user": h.message, "assistant": ""}
        elif h.role == "assistant":
            if current_exchange:
                current_exchange["assistant"] = h.message
                exchanges.append(current_exchange)
                current_exchange = {}
            else:
                exchanges.append({"user": "", "assistant": h.message})
    if current_exchange:
        exchanges.append(current_exchange)
    return exchanges

def delete_chat_history(person_id):
    db = SessionLocal()
    db.query(ChatHistory).filter(ChatHistory.person_id == person_id).delete()
    db.commit()
    db.close()

def update_user(user_id, first_name, last_name, job_title, native_language, english_level, personality_traits, profile_photo_bytes, transcript_files, audio_files):
    db = SessionLocal()
    user = db.query(Person).filter(Person.id == user_id).first()
    if user:
        user.first_name = first_name
        user.last_name = last_name
        user.job_title = job_title
        user.native_language = native_language
        user.english_level = english_level
        user.personality_traits = personality_traits
        if profile_photo_bytes:
            user.profile_photo = profile_photo_bytes
        # Remove existing transcript files
        db.query(Transcript).filter(Transcript.person_id == user_id).delete()
        for file_name, file_content in transcript_files:
            transcript = Transcript(person_id=user.id, file_name=file_name, file_content=file_content)
            db.add(transcript)
        # Remove existing audio files
        db.query(Audio).filter(Audio.person_id == user_id).delete()
        for file_name, file_content in audio_files:
            audio = Audio(person_id=user.id, file_name=file_name, file_content=file_content)
            db.add(audio)
        db.commit()
    db.close()

def delete_user(user_id):
    db = SessionLocal()
    db.query(Person).filter(Person.id == user_id).delete()
    db.commit()
    db.close()
    
def get_user_transcripts(person_id):
    """
    Return a list of existing transcripts for the given user_id.
    Each transcript is returned as a dict with filename and file_content.
    """
    db = SessionLocal()
    transcripts = db.query(Transcript).filter(Transcript.person_id == person_id).all()
    result = [
        {
            "filename": t.file_name,
            "file_content": t.file_content
        }
        for t in transcripts
    ]
    db.close()
    return result

def get_user_audios(person_id):
    """
    Return a list of existing audio files for the given user_id.
    Each audio file is returned as a dict with filename and file_content.
    """
    db = SessionLocal()
    audios = db.query(Audio).filter(Audio.person_id == person_id).all()
    result = [
        {
            "filename": a.file_name,
            "file_content": a.file_content
        }
        for a in audios
    ]
    db.close()
    return result

def remove_profile_photo(user_id):
    """
    Sets the user's profile_photo to None in the database.
    """
    db = SessionLocal()
    user = db.query(Person).filter(Person.id == user_id).first()
    if user:
        user.profile_photo = None
        db.commit()
    db.close()

def remove_transcript(user_id, transcript_filename):
    """
    Removes a specific transcript by filename for the given user_id.
    """
    db = SessionLocal()
    db.query(Transcript).filter(
        Transcript.person_id == user_id,
        Transcript.file_name == transcript_filename
    ).delete()
    db.commit()
    db.close()

def remove_audio(user_id, audio_filename):
    """
    Removes a specific audio file by filename for the given user_id.
    """
    db = SessionLocal()
    db.query(Audio).filter(
        Audio.person_id == user_id,
        Audio.file_name == audio_filename
    ).delete()
    db.commit()
    db.close()

init_db()
