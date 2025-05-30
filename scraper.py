import requests
from bs4 import BeautifulSoup
import sqlite3

BASE_URL = "https://nutrition.umd.edu/"
DINING_HALL_ID_DICT = {
    "South Campus": 16,
    "Yahentamitsi Dining Hall": 19,
    "251 North": 51
}
meal_id_map = {
    "breakfast": "pane-1",
    "lunch": "pane-2",
    "dinner": "pane-3"
}

def create_tables():
    with sqlite3.connect('macro_tracker.db') as conn:
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS foods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                meal TEXT NOT NULL,
                dining_hall TEXT NOT NULL,
                station TEXT,
                date TEXT NOT NULL,
                UNIQUE (url, date, meal, dining_hall)
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS macros (
                food_id INTEGER PRIMARY KEY,
                protein REAL DEFAULT 0.0,
                carbs REAL DEFAULT 0.0,
                fat REAL DEFAULT 0.0,
                calories REAL DEFAULT 0.0,
                serving_size TEXT DEFAULT '',
                FOREIGN KEY(food_id) REFERENCES foods(id) ON DELETE CASCADE
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS macro_goals (
            user_id INTEGER PRIMARY KEY,
            calorie_goal REAL,
            protein_goal REAL,
            carbs_goal REAL,
            fat_goal REAL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            food_id INTEGER NOT NULL,
            quantity REAL DEFAULT 1.0,
            date TEXT NOT NULL,
            meal TEXT NOT NULL,
            FOREIGN KEY(food_id) REFERENCES foods(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """)

        conn.commit()


# menu logic
def get_all_urls(date, dining_hall):
    URL = f"{BASE_URL}?locationNum={DINING_HALL_ID_DICT[dining_hall]}&dtdate={date}"
    result = requests.get(URL)
    soup = BeautifulSoup(result.text, "html.parser")

    foods = []

    for meal_type, div_id in meal_id_map.items():
        container = soup.find(id=div_id)
        
        cards = container.find_all(class_="card")
        for card in cards:
            station_name = card.find('h5', class_="card-title").text.strip()

            for item in card.find_all(class_="menu-item-row"):
                food_item = item.find('a', class_="menu-item-name", href=True)
                food_name = food_item.text.strip()
                food_url = BASE_URL + food_item['href']

                food_item_allergen_section = item.find(class_="col-md-4")
                food_allergens = []

                if food_item_allergen_section:
                    food_item_allergen = food_item_allergen_section.find_all(class_="nutri-icon")
                    # LIST of all the allergens
                    food_allergens = [allergen["title"] for allergen in food_item_allergen]


                foods.append({
                    "name": food_name,
                    "url": food_url,
                    "meal": meal_type,
                    "dining_hall": dining_hall,
                    "station": station_name,
                    "date": date,
                    "allergens": food_allergens
                })
    
    return foods

def get_macros(url):
    result = requests.get(url)
    soup = BeautifulSoup(result.text, "html.parser")

    # get name
    name = soup.find("h2").text.strip() if soup.find("h2") else None
    # get serving size
    serving_sizes = soup.find_all("div", class_="nutfactsservsize")
    serving_size = serving_sizes[1].text.strip() if len(serving_sizes) > 1 else None 
    # get macros
    protein = None
    carbs = None
    fat = None
    calories = None

    nutrition_facts = soup.find_all(class_="nutfactstopnutrient")
    for fact in nutrition_facts:
        text = fact.text.lower().replace("\xa0", " ").strip()
        if "protein" in text:
            try:
                protein = float(text.split()[1].replace("g", ""))
            except:
                pass
        elif "total carbohydrate" in text:
            try:
                carbs = float(text.split()[2].replace("g", ""))
            except:
                pass
        elif "total fat" in text:
            try:
                fat = float(text.split()[2].replace("g", ""))
            except:
                pass
        elif "calories" in text and calories == None:
            try:
                calories = float(text.split()[1].replace("kcal", ""))
            except:
                pass



    return {
        "name": name,
        "url": url,
        "serving_size": serving_size or 0.0,
        "protein": protein or 0.0,
        "carbs": carbs or 0.0,
        "fat": fat or 0.0,
        "calories": calories or 0.0
    }

def insert_foods_and_macros(foods):
    with sqlite3.connect("macro_tracker.db") as conn:
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()

        for food in foods:
            # Try inserting the food
            try:
                cursor.execute("""
                    INSERT INTO foods (name, url, meal, dining_hall, station, date) 
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (food["name"], food["url"], food["meal"], food["dining_hall"], food["station"], food["date"]))
                conn.commit()
                print(f"Inserted new food: {food['name']}")
            except sqlite3.IntegrityError:
                print(f"Duplicate found: {food['name']}, skipping food insert")

            # Only fetch macros if not already in macros table
            cursor.execute("""
                SELECT id FROM foods 
                WHERE url = ? AND id NOT IN (SELECT food_id FROM macros)
            """, (food["url"],))
            row = cursor.fetchone()

            if row:
                food_id = row[0]
                macros = get_macros(food["url"])

                cursor.execute("""
                    INSERT INTO macros (food_id, protein, carbs, fat, calories, serving_size)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    food_id,
                    macros.get("protein", 0.0),
                    macros.get("carbs", 0.0),
                    macros.get("fat", 0.0),
                    macros.get("calories", 0.0),
                    macros.get("serving_size", '')
                ))
                conn.commit()
                print(f"Inserted macros for food ID {food_id}: {macros['name']}")
            else:
                print(f"Macros already exist or food not found for URL: {food['url']}")
        
def get_food_name_by_id(food_id):
    with sqlite3.connect("macro_tracker.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM foods WHERE id = ?", (food_id,))
        result = cursor.fetchone()
        return result[0] if result else None

def get_foods_by_meal(meal_type, date, dining_hall):
    query = "SELECT id, name, station FROM foods WHERE meal = ? AND date = ? AND dining_hall = ?"

    with sqlite3.connect("macro_tracker.db") as conn:
        cursor = conn.cursor()
        cursor.execute(query, (meal_type, date, dining_hall))
        results = cursor.fetchall()

    grouped = {}
    for food_id, name, station in results:
        if station not in grouped:
            grouped[station] = []
        grouped[station].append((food_id, name))
    
    return grouped


# user logic
def add_user(username, email):
    query = "INSERT INTO users (username, email) VALUES (?, ?)"

    try:
        with sqlite3.connect("macro_tracker.db") as conn:
            cursor = conn.cursor()
            cursor.execute(query, (username, email))
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

def validate_account(username, email):
    with sqlite3.connect("macro_tracker.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT email FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()

        if row is None:
            return False
        return row[0] == email


def set_macro_goals(user_id, calories, protein, carbs, fat):
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

def update_log(log_id, quantity, date, meal):
    with sqlite3.connect("macro_tracker.db") as conn:
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE logs 
            SET quantity = ?, date = ?, meal = ?
            WHERE id = ?
        """, (quantity, date, meal, log_id))

    conn.commit()






# CLI functions
def login():
    while True:
        username = input("Enter your username: ")
        user = get_user_by_username(username)
        if user:
            email = input("Enter your email: ")
            if user[2] == email:
                print(f"Welcome back {username}")
                return user
            else:
                print("Email is not found or not associate with this username. Please try again.")
        else:
            print("Username is not found. Please try again.")

def register():
    while True:
        username = input("Create a username: ")
        if username_exists(username):
            print(f"The username {username} is already taken.")
            continue
            
        email = input("Enter an email: ")
        if email_exists(email):
            print(f"The email {email} is already taken.")
            continue

        with sqlite3.connect("macro_tracker.db") as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (username, email) VALUES (?, ?)", (username, email))
            conn.commit()
            print(f"User {username} registered successfully.")
            return username

def welcome():
    while True:
        has_account = input("Do you have an account? (Y/N) ").strip().lower()
        if has_account == "y":
            user = login()
            return user
        elif has_account == "n":
            user = register()
            return user

        else:
            print("Invalid input. Please type either Y or N.")

def cli_log_food(user_id):
    food_id = int(input("Choose a food to log: ").strip())
    food_name = get_food_name_by_id(food_id)
    quantity = float(input("How many servings?: ").strip())
    date = "5/19/2025" # HARD CODED DATE
    meal_type = input("When did you eat this food? (breakfast, lunch, dinner): ").strip().lower()
    was_logged = log_food(user_id, food_id, quantity, date, meal_type) 
    if was_logged:
        print(f"{food_name} (x{quantity}) was successfully logged on {date} for {meal_type}.")
    else:
        print("Failed to log food.")

def cli_view_menu():
    date = "5/19/2025" # HARDCODED DATE
    dining_hall = "South Campus" # HARDCODED DINING HALL

    while True:
        meal_type = input("Which menu time? (breakfast, lunch, dinner): ").strip().lower()

        if meal_type == 'breakfast' or meal_type == 'lunch' or meal_type == 'dinner':
            for food_id, food_name in get_foods_by_meal(meal_type, date, dining_hall):
                print(f"{food_id}) {food_name}")
            break
        else:
            print("Invalid meal type. Please try again.")

def cli_set_macro_goals(user_id):
    while True:
        try:
            calories_goal = float(input("What is your calories goal? ").strip())
            protein_goal = float(input("What is your protein goal? ").strip())
            carbs_goal = float(input("What is your carbs goal? ").strip())
            fat_goal = float(input("What is your fat goal? ").strip())
        except ValueError:
            print("Please enter valid numbers.")
            continue
        
        was_set = set_macro_goals(user_id, calories_goal, protein_goal, carbs_goal, fat_goal)
        if was_set:
            print(f"Macro goals successfully set to: {calories_goal} calories, {protein_goal}g protein, {carbs_goal}g carbs, {fat_goal}g fat.")
            break
        else:
            print("Failed to set macro goals.")

def cli_view_daily_macros(user_id):
    date = "5/19/2025" # HARDCODED DATE
    total = get_daily_macros(user_id, date, False)
    print(f"You have eaten {total["calories"]} calories, {total["protein"]}g protein, {total["carbs"]}g carbs, and {total["fat"]}g fat.")

def cli_view_remaining_macros(user_id):
    date = "5/19/2025" # HARDCODED DATE
    remaining_macros = get_remaining_macros(user_id, date)
    print(f"Remaining macros: {remaining_macros['calories_remaining']} calories, {remaining_macros['protein_remaining']}g protein, {remaining_macros['carbs_remaining']}g carbs, {remaining_macros['fat_remaining']}g fat.")

def cli_view_logged_foods(user_id):
    date = "5/19/2025" #HARDCODED DATE
    foods, total = get_daily_macros(user_id, date)
    for food in foods:
        print(f"Log #{food['log_id']} - {food['meal']} - {food['name']} (x{food['quantity']})")

def cli_main():
    while True:
        print("\n=== Macro Tracker Menu ===")
        print("1. Log a food")
        print("2. View menu")
        print("3. Set macro goals")
        print("4. View macros eaten for today")
        print("5. View remaining macros for today")
        print("6. View today's logged foods")
        print("7. Remove a food from log")
        print("8. Quit")

        choice = input("Select an option (1-8): ").strip()

        if choice == '1':
            cli_log_food(user_id)
        elif choice == '2':
            cli_view_menu()
        elif choice == '3':
            cli_set_macro_goals(user_id)
        elif choice == '4':
            cli_view_daily_macros(user_id)
        elif choice == '5':
            cli_view_remaining_macros(user_id)
        elif choice == '6':
            cli_view_logged_foods(user_id)
        elif choice == '7':
            id = input("Which food would you like to remove? (id): ")
            food_name = get_food_name_by_id(id)
            was_removed = remove_log_by_id(id)
            if was_removed:
                print(f"{food_name} was successfully removed from the log.")
            else:
                print("Failed to remove the food log.")
        elif choice == '8':
            print("User chose to quit")
            break
        else:
            print("Invalid input.")

if __name__ == "__main__":
    user = welcome()
    user_id = user[0]
    cli_main()

    
