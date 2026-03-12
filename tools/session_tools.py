import json
from sqlalchemy import create_engine, text

class SessionTools:
    def __init__(self, db_url: str):
        self.engine = create_engine(db_url, pool_size=10, max_overflow=20)

    def verify_or_create_table(self):
        with self.engine.begin() as conn:
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

    def update_transcript(self, session_id: str, transcript: str, language: str):
        try:
            new_msg = json.dumps([{"speaker": "caller", "text": transcript}])
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
                
                if result.rowcount > 0:
                    print("Saved to session")
                    
        except Exception as e:
            pass