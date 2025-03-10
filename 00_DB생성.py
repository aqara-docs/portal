# Pain Button 관련 테이블 생성
cursor.execute("""
    CREATE TABLE IF NOT EXISTS dot_pain_events (
        event_id INT AUTO_INCREMENT PRIMARY KEY,
        user_id INT NOT NULL,
        target_user_id INT NOT NULL,
        meeting_id INT NOT NULL,
        pain_level INT NOT NULL CHECK (pain_level BETWEEN 1 AND 5),
        reason TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES dot_user_credibility(user_id),
        FOREIGN KEY (target_user_id) REFERENCES dot_user_credibility(user_id),
        FOREIGN KEY (meeting_id) REFERENCES dot_meetings(meeting_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS dot_pain_stats (
        user_id INT PRIMARY KEY,
        total_pain_received INT DEFAULT 0,
        avg_pain_level FLOAT DEFAULT 0,
        last_pain_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES dot_user_credibility(user_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
""") 