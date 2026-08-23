"""
Database seeder for CareFlow.
Seeds initial sample doctors and default data into relational tables.
"""
import uuid
import hashlib
import os
from datetime import datetime, timezone
from .db import get_db

SECRET = os.getenv('APP_SECRET', 'change-this-in-production')


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def hash_password(password: str) -> str:
    return hashlib.sha256((SECRET + '|' + password).encode()).hexdigest()


def seed_initial_data():
    """Seeds doctors and default users if the users table is empty."""
    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users LIMIT 1")
        if cur.fetchone():
            return  # Already seeded

        # Seed initial doctors
        doc1_id, doc2_id, doc3_id = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        cur.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
            (doc1_id, 'Dr. Ananya Rao', 'ananya.rao@careflow.demo', hash_password('x'), 'doctor', now_iso())
        )
        cur.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
            (doc2_id, 'Dr. Vikram Shah', 'vikram.shah@careflow.demo', hash_password('x'), 'doctor', now_iso())
        )
        cur.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
            (doc3_id, 'Dr. Priya Nair', 'priya.nair@careflow.demo', hash_password('x'), 'doctor', now_iso())
        )

        cur.execute(
            "INSERT INTO doctors(user_id, specialization, working_days, start_time, end_time, slot_minutes, leave_days) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (doc1_id, 'General Medicine', 'Mon,Tue,Wed,Thu,Fri', '09:00', '17:00', 30, '[]')
        )
        cur.execute(
            "INSERT INTO doctors(user_id, specialization, working_days, start_time, end_time, slot_minutes, leave_days) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (doc2_id, 'Cardiology', 'Mon,Wed,Fri', '10:00', '16:00', 20, '[]')
        )
        cur.execute(
            "INSERT INTO doctors(user_id, specialization, working_days, start_time, end_time, slot_minutes, leave_days) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (doc3_id, 'Dermatology', 'Tue,Wed,Thu,Fri,Sat', '11:00', '18:00', 15, '[]')
        )

        conn.commit()
    finally:
        conn.close()


if __name__ == '__main__':
    from .db import init_database
    init_database()
    print("Database tables initialized and initial data seeded successfully.")
