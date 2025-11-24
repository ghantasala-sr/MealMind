import hashlib
import uuid

def hash_password(password):
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()


def create_user_account(conn, username, password, email=None):
    """Create new user account"""
    cursor = conn.cursor()
    user_id = str(uuid.uuid4())
    password_hash = hash_password(password)

    try:
        cursor.execute("""
                       INSERT INTO users (user_id, username, password_hash, email, profile_completed)
                       VALUES (%s, %s, %s, %s, FALSE)
                       """, (user_id, username, password_hash, email))
        conn.commit()
        cursor.close()
        return True, user_id
    except Exception as e:
        cursor.close()
        if "unique constraint" in str(e).lower():
            return False, "Username already exists"
        return False, str(e)


def authenticate_user(conn, username, password):
    """Authenticate user login"""
    cursor = conn.cursor()
    password_hash = hash_password(password)

    cursor.execute("""
                   SELECT user_id, username, profile_completed
                   FROM users
                   WHERE username = %s
                     AND password_hash = %s
                   """, (username, password_hash))

    result = cursor.fetchone()

    if result:
        cursor.execute("""
                       UPDATE users
                       SET last_login = CURRENT_TIMESTAMP()
                       WHERE user_id = %s
                       """, (result[0],))
        conn.commit()
        cursor.close()
        return True, result[0], result[1], result[2]

    cursor.close()
    return False, None, None, None
