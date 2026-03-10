import json
from sqlalchemy import create_engine, text

class SessionTools:
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url)

    def verify_or_create_table(self):
        """Ensures the calls table exists for testing purposes."""
        with self.engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS calls (
                    session_id VARCHAR(255) PRIMARY KEY,
                    session_data JSONB NOT NULL
                )
            """))
            conn.commit()

    def create_dummy_session(self, session_id: str, dummy_data: dict):
        """Inserts a dummy session for testing."""
        self.verify_or_create_table()
        with self.engine.connect() as conn:
            # Check if session exists
            result = conn.execute(
                text("SELECT 1 FROM calls WHERE session_id = :session_id"),
                {"session_id": session_id}
            ).fetchone()

            if not result:
                conn.execute(
                    text("INSERT INTO calls (session_id, session_data) VALUES (:session_id, :session_data)"),
                    {"session_id": session_id, "session_data": json.dumps(dummy_data)}
                )
                conn.commit()
                print(f"✅ Created dummy session: {session_id}")
            else:
                print(f"ℹ️  Session {session_id} already exists.")

    def update_transcript(self, session_id: str, transcript: str, language: str):
        """
        Updates the PostgreSQL JSONB session_data.
        Appends the new message to 'state.conversation' array.
        Updates 'state.language' to the detected language.
        """
        with self.engine.connect() as conn:
            # Prepare the new conversation item
            new_msg = {"speaker": "caller", "text": transcript}
            
            # First, get the current session data
            result = conn.execute(
                text("SELECT session_data FROM calls WHERE session_id = :session_id"),
                {"session_id": session_id}
            ).fetchone()
            
            if not result:
                print(f"❌ Session {session_id} not found")
                return
                
            session_data = result[0]
            
            # Update the conversation array and language
            if 'state' not in session_data:
                session_data['state'] = {}
                
            if 'conversation' not in session_data['state']:
                session_data['state']['conversation'] = []
                
            # Append new message to conversation
            session_data['state']['conversation'].append(new_msg)
            session_data['state']['language'] = language
            
            # Update the entire session_data
            conn.execute(
                text("UPDATE calls SET session_data = :session_data WHERE session_id = :session_id"),
                {"session_id": session_id, "session_data": json.dumps(session_data)}
            )
            conn.commit()
            print(f"💾 Saved to DB | Session: {session_id} | Lang: {language} | Text: {transcript}")
