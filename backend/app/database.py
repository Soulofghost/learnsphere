import sqlite3
import datetime
import json
import uuid
from typing import Optional
from backend.app.config import DB_PATH

def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    if not path.startswith(":memory:") and "mode=memory" not in path:
        conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db(db_path: Optional[str] = None):
    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS courses (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        description TEXT NOT NULL,
        category TEXT NOT NULL,
        level TEXT NOT NULL,
        instructor TEXT NOT NULL,
        duration_hours REAL NOT NULL,
        created_at TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS modules (
        id TEXT PRIMARY KEY,
        course_id TEXT NOT NULL,
        title TEXT NOT NULL,
        sequence_order INTEGER NOT NULL,
        content TEXT NOT NULL,
        duration_minutes INTEGER NOT NULL,
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quizzes (
        id TEXT PRIMARY KEY,
        course_id TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        passing_score_pct REAL DEFAULT 75.0,
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quiz_questions (
        id TEXT PRIMARY KEY,
        quiz_id TEXT NOT NULL,
        question_text TEXT NOT NULL,
        options_json TEXT NOT NULL,
        correct_option_index INTEGER NOT NULL,
        explanation TEXT NOT NULL,
        FOREIGN KEY (quiz_id) REFERENCES quizzes(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS enrollments (
        id TEXT PRIMARY KEY,
        user_email TEXT NOT NULL,
        user_name TEXT NOT NULL,
        course_id TEXT NOT NULL,
        progress_pct REAL DEFAULT 0.0,
        completed_modules_json TEXT DEFAULT '[]',
        is_completed INTEGER DEFAULT 0,
        enrolled_at TEXT NOT NULL,
        completed_at TEXT,
        UNIQUE (user_email, course_id),
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS certificates (
        id TEXT PRIMARY KEY,
        cert_code TEXT UNIQUE NOT NULL,
        user_name TEXT NOT NULL,
        user_email TEXT NOT NULL,
        course_id TEXT NOT NULL,
        score_pct REAL NOT NULL,
        issued_at TEXT NOT NULL,
        FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
    );
    """)

    # Seed Courses if empty
    cursor.execute("SELECT COUNT(*) FROM courses;")
    if cursor.fetchone()[0] == 0:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # Course 1: Distributed Systems
        c1_id = "c101-dist-sys"
        cursor.execute("""
        INSERT INTO courses (id, title, slug, description, category, level, instructor, duration_hours, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            c1_id,
            "Distributed Systems & Cloud Architecture",
            "distributed-systems-cloud",
            "Master consensus algorithms, CAP theorem trade-offs, partitioned replication, and cloud-native resilience.",
            "Cloud Engineering",
            "Advanced",
            "Dr. Aris Thorne",
            12.5,
            now
        ))

        modules_c1 = [
            (str(uuid.uuid4()), c1_id, "Consensus Protocols: Paxos and Raft", 1, "Deep dive into leader election, term numbering, and replicated log state machines.", 45),
            (str(uuid.uuid4()), c1_id, "Distributed Transactions & 2PC/3PC", 2, "Two-phase commit coordinator states, abort decisions, and Saga compensation patterns.", 50),
            (str(uuid.uuid4()), c1_id, "Consistent Hashing & Dynamic Sharding", 3, "Virtual node distribution, ring topologies, and zero-downtime rebalancing.", 40),
            (str(uuid.uuid4()), c1_id, "Fault Tolerance & Byzantine Generals", 4, "Crash-stop vs crash-recovery vs Byzantine fault models in geo-distributed clusters.", 55),
        ]
        cursor.executemany("""
        INSERT INTO modules (id, course_id, title, sequence_order, content, duration_minutes)
        VALUES (?, ?, ?, ?, ?, ?);
        """, modules_c1)

        q1_id = str(uuid.uuid4())
        cursor.execute("INSERT INTO quizzes (id, course_id, title, passing_score_pct) VALUES (?, ?, ?, 75.0);",
                       (q1_id, c1_id, "Final Mastery Assessment: Distributed Systems"))

        questions_c1 = [
            (str(uuid.uuid4()), q1_id, "In the Raft consensus algorithm, how does a candidate node transition to a leader?",
             json.dumps(["By receiving votes from a majority (quorum) of cluster nodes", "By having the lowest node ID", "By having the largest disk capacity", "Through a round-robin schedule"]),
             0, "Raft requires a candidate to receive a majority quorum of node votes in the current election term to become leader."),
            (str(uuid.uuid4()), q1_id, "According to the CAP Theorem, what does a system guarantee during network partition in CP mode?",
             json.dumps(["High latency responses for all clients", "Consistency and Partition tolerance while sacrificing availability", "Eventual availability without data guarantees", "Zero packet loss"]),
             1, "Under network partition (P), a CP system denies inconsistent read/write operations to preserve linearizable consistency."),
            (str(uuid.uuid4()), q1_id, "What is the primary vulnerability of standard Two-Phase Commit (2PC)?",
             json.dumps(["No locking required", "Coordinator failure during the commit phase blocks participants indefinitely", "Inability to support SQL databases", "Excessive CPU overhead"]),
             1, "2PC is a blocking protocol: if the coordinator crashes while participants are in the prepared state, participants remain blocked."),
            (str(uuid.uuid4()), q1_id, "Why are virtual nodes utilized in consistent hashing rings?",
             json.dumps(["To eliminate encryption requirements", "To achieve uniform key distribution across heterogeneous physical servers", "To increase memory bandwidth", "To speed up DNS queries"]),
             1, "Virtual nodes prevent hot-spots and ensure an even, uniform statistical distribution of hash tokens across physical servers.")
        ]
        cursor.executemany("""
        INSERT INTO quiz_questions (id, quiz_id, question_text, options_json, correct_option_index, explanation)
        VALUES (?, ?, ?, ?, ?, ?);
        """, questions_c1)

        # Course 2: Applied Machine Learning
        c2_id = "c102-applied-ml"
        cursor.execute("""
        INSERT INTO courses (id, title, slug, description, category, level, instructor, duration_hours, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            c2_id,
            "Applied Machine Learning with PyTorch",
            "applied-ml-pytorch",
            "Production neural network modeling, gradient backpropagation, attention mechanisms, and model evaluation.",
            "Artificial Intelligence",
            "Intermediate",
            "Prof. Sarah Lin",
            16.0,
            now
        ))

        modules_c2 = [
            (str(uuid.uuid4()), c2_id, "Tensors, Autograd & Computational Graphs", 1, "PyTorch dynamic computational DAGs, autograd engine, and backward passes.", 45),
            (str(uuid.uuid4()), c2_id, "Transformer Attention Mechanisms", 2, "Scaled dot-product attention, multi-head projections, and positional encodings.", 60),
            (str(uuid.uuid4()), c2_id, "Loss Formulations & Regularization", 3, "Cross-entropy, Focal loss, AdamW optimizer weight decay, and dropout dynamics.", 50)
        ]
        cursor.executemany("""
        INSERT INTO modules (id, course_id, title, sequence_order, content, duration_minutes)
        VALUES (?, ?, ?, ?, ?, ?);
        """, modules_c2)

        q2_id = str(uuid.uuid4())
        cursor.execute("INSERT INTO quizzes (id, course_id, title, passing_score_pct) VALUES (?, ?, ?, 75.0);",
                       (q2_id, c2_id, "Final Mastery Assessment: Applied ML"))

        questions_c2 = [
            (str(uuid.uuid4()), q2_id, "What is the computational complexity of standard self-attention with sequence length N?",
             json.dumps(["O(N log N)", "O(N^2)", "O(N)", "O(2^N)"]),
             1, "Pairwise dot-product attention requires computing an N x N matrix, resulting in quadratic O(N^2) complexity with sequence length."),
            (str(uuid.uuid4()), q2_id, "Why is gradient clipping employed during recurrent neural network training?",
             json.dumps(["To mitigate exploding gradients", "To reduce RAM usage", "To accelerate learning rate decay", "To initialize weights randomly"]),
             0, "Gradient clipping caps gradient norms to a maximum threshold, preventing numerical overflow and exploding gradients during backpropagation."),
            (str(uuid.uuid4()), q2_id, "In PyTorch, what does `model.eval()` specifically modify?",
             json.dumps(["Freezes all trainable weights permanently", "Disables layers with different train/inference behaviors such as Dropout and BatchNorm", "Deletes intermediate gradients from memory", "Converts model to ONNX"]),
             1, "`model.eval()` toggles evaluation mode for layers like Dropout (which becomes identity) and BatchNorm (which uses running statistics).")
        ]
        cursor.executemany("""
        INSERT INTO quiz_questions (id, quiz_id, question_text, options_json, correct_option_index, explanation)
        VALUES (?, ?, ?, ?, ?, ?);
        """, questions_c2)

    conn.commit()
    return conn
