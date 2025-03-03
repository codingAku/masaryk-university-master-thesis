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
    transcript_files = Column(LargeBinary)
    # Relationship to chat history
    chat_history = relationship("ChatHistory", back_populates="person", cascade="all, delete-orphan")

class ChatHistory(Base):
    __tablename__ = "chat_history"
    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("person.id"), nullable=False)
    role = Column(String, nullable=False)  # "user" or "assistant"
    message = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    
    person = relationship("Person", back_populates="chat_history")

def init_db():
    Base.metadata.create_all(bind=engine)

def add_user(first_name, last_name, job_title, native_language, english_level, personality_traits, profile_photo_bytes, transcript_bytes):
    db = SessionLocal()
    new_person = Person(
        first_name=first_name,
        last_name=last_name,
        job_title=job_title,
        native_language=native_language,
        english_level=english_level,
        personality_traits=personality_traits,
        profile_photo=profile_photo_bytes,
        transcript_files=transcript_bytes,
    )
    db.add(new_person)
    db.commit()
    db.refresh(new_person)
    db.close()
    return new_person

def get_users():
    db = SessionLocal()
    users = db.query(Person).all()
    db.close()
    return [
        {
            "id": user.id,
            "name": f"{user.first_name} {user.last_name}",
            "job": user.job_title,
            "profile_photo": user.profile_photo
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
    # Group the messages into exchanges. We assume each user message is followed by an assistant reply.
    exchanges = []
    current_exchange = {}
    for h in history:
        if h.role == "user":
            # If a previous exchange exists without an assistant reply, add it.
            if current_exchange:
                exchanges.append(current_exchange)
            current_exchange = {"user": h.message, "assistant": ""}
        elif h.role == "assistant":
            if current_exchange:
                current_exchange["assistant"] = h.message
                exchanges.append(current_exchange)
                current_exchange = {}
            else:
                # In case of an orphan assistant message.
                exchanges.append({"user": "", "assistant": h.message})
    # If an exchange is incomplete, add it as well.
    if current_exchange:
        exchanges.append(current_exchange)
    return exchanges

# Initialize the database tables on module import.
init_db()
