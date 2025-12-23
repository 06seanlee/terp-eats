import sqlite3
from werkzeug.security import check_password_hash


def get_food_name_by_id(food_id):
    with sqlite3.connect("macro_tracker.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM foods WHERE id = ?", (food_id,))
        result = cursor.fetchone()
        return result[0] if result else None

def get_foods_by_meal(meal_type, date, dining_hall):
    query = """
        SELECT 
            f.id,
            f.name,
            f.serving_size,
            m.station,
            f.protein,
            f.carbs,
            f.fat,
            f.calories
        FROM menus m
        JOIN foods f ON m.food_id = f.id
        WHERE m.meal_type = ?
          AND m.date = ?
          AND m.location = ?
        ORDER BY m.station, f.name
    """

    with sqlite3.connect("macro_tracker.db") as conn:
        cursor = conn.cursor()
        cursor.execute(query, (meal_type, date, dining_hall))
        results = cursor.fetchall()

    grouped = {}
    for food_id, name, serving_size, station, protein, carbs, fat, calories in results:
        if station not in grouped:
            grouped[station] = []

        grouped[station].append({
            "id": food_id,
            "name": name,
            "serving_size": serving_size,
            "protein": protein,
            "carbs": carbs,
            "fat": fat,
            "calories": calories
        })

    return grouped


# database.py used for querying database and updating logs/goals/users

# user logic
def add_user(username, email, password):
    query = "INSERT INTO users (username, email, password) VALUES (?, ?, ?)"

    try:
        with sqlite3.connect("macro_tracker.db") as conn:
            cursor = conn.cursor()
            cursor.execute(query, (username, email, password))
            conn.commit()
            return cursor.lastrowid  # return new user's ID
    except sqlite3.IntegrityError:
        print(f"Username '{username}' already exists.")
        return None
    
def get_user_by_username(username):
    query = "SELECT id, username, email, created_at FROM users WHERE username = ?"
    with sqlite3.connect("macro_tracker.db") as conn:
        cursor = conn.cursor()
        cursor.execute(query, (username,))
        return cursor.fetchone()  # returns (id, username, email, created_at) or None

def get_user_by_id(id):
    query = "SELECT id, username, email, created_at FROM users WHERE id = ?"
    with sqlite3.connect("macro_tracker.db") as conn:
        cursor = conn.cursor()
        cursor.execute(query, (id,))
        return cursor.fetchone()

def remove_user(username):
    query = "DELETE FROM users WHERE username = ?"
    with sqlite3.connect("macro_tracker.db") as conn:
        cursor = conn.cursor()
        cursor.execute(query, (username,))
        conn.commit()

def update_user_username(old_username, new_username):
    query = "UPDATE users SET username = ? WHERE username = ?"
    with sqlite3.connect("macro_tracker.db") as conn:
        cursor = conn.cursor()
        cursor.execute(query, (new_username, old_username))
        conn.commit()

def update_user_email(username, new_email):
    query = "UPDATE users SET email = ? WHERE username = ?"
    with sqlite3.connect("macro_tracker.db") as conn:
        cursor = conn.cursor()
        cursor.execute(query, (new_email, username))
        conn.commit()

def username_exists(username):
    with sqlite3.connect("macro_tracker.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE username = ?", (username,))
        return cursor.fetchone() is not None

def email_exists(email):
    with sqlite3.connect("macro_tracker.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE email = ?", (email,))
        return cursor.fetchone() is not None

def validate_account(username, email, password):
    with sqlite3.connect("macro_tracker.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM users WHERE username = ? AND email = ?", (username, email))
        row = cursor.fetchone()

        if row is None:
            return False
        
        stored_password = row[0]
        return check_password_hash(stored_password, password)


def set_macro_goals(user_id, calories, protein, carbs, fat):
    try:
        values = [int(calories), int(protein), int(carbs), int(fat)]
    except ValueError:
        return False 

    if not all(num > 0 for num in values):
        return False
    

    try:
        with sqlite3.connect("macro_tracker.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO macro_goals (user_id, calorie_goal, protein_goal, carbs_goal, fat_goal)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    calorie_goal = excluded.calorie_goal,
                    protein_goal = excluded.protein_goal,
                    carbs_goal = excluded.carbs_goal,
                    fat_goal = excluded.fat_goal
            """, (user_id, calories, protein, carbs, fat))
            conn.commit()
            return True
    except sqlite3.IntegrityError as e:
        print(f"Failed to set macro goals due to error {e}")
        return False

def get_macro_goals(user_id):
    with sqlite3.connect("macro_tracker.db") as conn:
        cursor = conn.cursor()
        
        # Get macro goals
        cursor.execute("""
            SELECT calorie_goal, protein_goal, carbs_goal, fat_goal
            FROM macro_goals
            WHERE user_id = ?
        """, (user_id,))
        goal = cursor.fetchone()

        if not goal:
            return None  # No goals set for this user

        return goal
    
def get_daily_macros(user_id, date, return_foods=True):
    query = """
    SELECT
        f.name,
        l.quantity,
        m.calories * l.quantity AS total_calories,
        m.protein * l.quantity AS total_protein,
        m.carbs * l.quantity AS total_carbs,
        m.fat * l.quantity AS total_fat,
        l.meal,
        l.id
    FROM logs l
    JOIN foods f ON l.food_id = f.id
    JOIN macros m on f.id = m.food_id
    WHERE l.user_id = ? AND l.date = ?
    ORDER BY l.meal
    """

    with sqlite3.connect("macro_tracker.db") as conn:
        cursor = conn.cursor()
        cursor.execute(query, (user_id, date))
        rows = cursor.fetchall()
    
    if not rows:
        print("No logs found for this date and user")
    
    foods = []
    total_cals = total_protein = total_carbs = total_fat = 0

    for name, quantity, calories, protein, carbs, fat, meal, log_id in rows:
        calories = round(calories, 1)
        protein = round(protein, 1)
        carbs = round(carbs, 1)
        fat = round(fat, 1)

        foods.append({
            "name": name,
            "quantity": quantity,
            "calories": calories,
            "protein": protein,
            "carbs": carbs,
            "fat": fat,
            "meal": meal,
            "log_id": log_id
        })
        
        total_cals += calories
        total_protein += protein
        total_carbs += carbs
        total_fat += fat

    total = {
        "calories": round(total_cals, 1),
        "protein": round(total_protein, 1),
        "carbs": round(total_carbs, 1),
        "fat": round(total_fat, 1)
    }

    return (foods, total) if return_foods else total

def get_remaining_macros(user_id, date):
    goal = get_macro_goals(user_id)

    if not goal:
        print(f"No goals set for this user {user_id}")
        return 

    total = get_daily_macros(user_id, date, False)

    cal_goal, protein_goal, carbs_goal, fat_goal = goal

    total_cals = total["calories"] or 0
    total_protein = total["protein"] or 0
    total_carbs = total["carbs"] or 0
    total_fat = total["fat"] or 0

    return {
        "calories_remaining": round(cal_goal - total_cals, 1),
        "protein_remaining": round(protein_goal - total_protein, 1),
        "carbs_remaining": round(carbs_goal - total_carbs, 1),
        "fat_remaining": round(fat_goal - total_fat, 1)
    }

def log_food(user_id, food_id, quantity, date, meal):
    query = """
        INSERT INTO logs (user_id, food_id, quantity, date, meal)
        VALUES (?, ?, ?, ?, ?)
    """

    with sqlite3.connect("macro_tracker.db") as conn:
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()

        cursor.execute("SELECT 1 FROM users WHERE id = ?", (user_id,))
        if cursor.fetchone() is None:
            print(f"User ID {user_id} does not exist. Cannot log food.")
            return False
        
        cursor.execute("SELECT 1 FROM foods WHERE id = ?", (food_id,))
        if cursor.fetchone() is None:
            print(f"Food ID {food_id} does not exist. Cannot log food.")
            return False

        cursor.execute(query, (user_id, food_id, quantity, date ,meal))
        conn.commit()
        return True

def remove_log_by_id(id):
    with sqlite3.connect("macro_tracker.db") as conn:
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM logs WHERE id = ?
        """, (id,))

        conn.commit()
        return cursor.rowcount > 0

def remove_log_by_date(date):
    with sqlite3.connect("macro_tracker.db") as conn:
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM logs WHERE date = ?
        """, (date,))

    conn.commit()

def update_log(log_id, quantity, date):
    with sqlite3.connect("macro_tracker.db") as conn:
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE logs 
            SET quantity = ?, date = ?
            WHERE id = ?
        """, (quantity, date, log_id))

        conn.commit()