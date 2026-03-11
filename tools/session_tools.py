import json
import logging
from sqlalchemy import create_engine, text

logger = logging.getLogger(__name__)

class SessionTools:
    def __init__(self, db_url: str):
        # Enable connection pooling to handle high-concurrency DB writes
        self.engine = create_engine(db_url, pool_size=10, max_overflow=20)

    def verify_or_create_table(self):
        """Ensures the calls table matches your provided database schema."""
        with self.engine.begin() as conn:  # .begin() automatically commits
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS calls (
                    session_id VARCHAR(255) PRIMARY KEY,
                    session_data JSONB NOT NULL,
                    lead_score INTEGER,
                    lead_type TEXT,
                    call_summary TEXT
                )
            """))

    def create_dummy_session(self, session_id: str, dummy_data: dict):
        """Inserts a dummy session for testing."""
        self.verify_or_create_table()
        with self.engine.begin() as conn:
            result = conn.execute(
                text("SELECT 1 FROM calls WHERE session_id = :session_id"),
                {"session_id": session_id}
            ).fetchone()

            if not result:
                conn.execute(
                    text("INSERT INTO calls (session_id, session_data) VALUES (:session_id, CAST(:session_data AS JSONB))"),
                    {"session_id": session_id, "session_data": json.dumps(dummy_data)}
                )
                logger.info(f"✅ Created dummy session: {session_id}")
            else:
                logger.info(f"ℹ️ Session {session_id} already exists.")

    def update_transcript(self, session_id: str, transcript: str, language: str):
        """
        Updates the PostgreSQL JSONB session_data ATOMICALLY.
        """
        try:
            # We wrap the dict in a list so we can concatenate it to the JSONB array in SQL
            new_msg = json.dumps([{"speaker": "caller", "text": transcript}])
            
            # Atomic SQL update avoids Race Conditions when parallel transcripts arrive
            # Using standard CAST() instead of :: to prevent SQLAlchemy parameter parsing errors!
            sql = text("""
                UPDATE calls 
                SET session_data = jsonb_set(
                    jsonb_set(
                        session_data, 
                        '{state,conversation}', 
                        COALESCE(session_data->'state'->'conversation', CAST('[]' AS JSONB)) || CAST(:new_msg AS JSONB)
                    ),
                    '{state,language}',
                    to_jsonb(CAST(:language AS TEXT))
                )
                WHERE session_id = :session_id
            """)

            with self.engine.begin() as conn:
                result = conn.execute(sql, {
                    "new_msg": new_msg, 
                    "language": language, 
                    "session_id": session_id
                })
                
                if result.rowcount == 0:
                    logger.warning(f"❌ Session {session_id} not found in DB")
                else:
                    logger.info(f"💾 Saved to DB | Session: {session_id} | Lang: {language} | Text: {transcript}")
                    
        except Exception as e:
            logger.error(f"❌ Failed to update transcript in DB: {e}", exc_info=True)