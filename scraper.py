import requests
from bs4 import BeautifulSoup
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from werkzeug.security import check_password_hash
from datetime import date, datetime


BASE_URL = "https://nutrition.umd.edu/"
DINING_HALL_ID_DICT = {
    "South Campus": 16,
    "Yahentamitsi Dining Hall": 19,
    "251 North": 51
}


# creates sqlite db (one time use) (DOESN'T HAVE USER, MACRO_GOALS, AND LOGS YET)
def create_tables():
    with sqlite3.connect('macro_tracker.db') as conn:
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS foods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                protein REAL DEFAULT 0.0,
                carbs REAL DEFAULT 0.0,
                fat REAL DEFAULT 0.0,
                calories REAL DEFAULT 0.0,
                serving_size TEXT DEFAULT ''
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS menus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                food_id INTEGER NOT NULL,
                location TEXT NOT NULL,
                station TEXT NOT NULL,
                date TEXT NOT NULL,
                meal_type TEXT NOT NULL,
                FOREIGN KEY(food_id) REFERENCES foods(id) ON DELETE CASCADE,
                UNIQUE(food_id, location, date, meal_type)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scrape_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                menu_date TEXT NOT NULL,
                ran_at TEXT NOT NULL,
                status TEXT NOT NULL,
                foods_found INTEGER DEFAULT 0,
                new_foods INTEGER DEFAULT 0,
                menu_rows INTEGER DEFAULT 0
        )
        """)

        # TODO: USERS, MACRO_GOALS, and LOGS tables  

        # cursor.execute("""
        # CREATE TABLE IF NOT EXISTS users (
        #     id INTEGER PRIMARY KEY AUTOINCREMENT,
        #     username TEXT NOT NULL UNIQUE,
        #     email TEXT NOT NULL UNIQUE,
        #     password TEXT NOT NULL, 
        #     created_at TEXT DEFAULT CURRENT_TIMESTAMP
        # )
        # """)

        # cursor.execute("""
        # CREATE TABLE IF NOT EXISTS macro_goals (
        #     user_id INTEGER PRIMARY KEY,
        #     calorie_goal REAL,
        #     protein_goal REAL,
        #     carbs_goal REAL,
        #     fat_goal REAL,
        #     FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        # )
        # """)

        # cursor.execute("""
        # CREATE TABLE IF NOT EXISTS logs (
        #     id INTEGER PRIMARY KEY AUTOINCREMENT,
        #     user_id INTEGER NOT NULL,
        #     food_id INTEGER NOT NULL,
        #     quantity REAL DEFAULT 1.0,
        #     date TEXT NOT NULL,
        #     meal TEXT NOT NULL,
        #     FOREIGN KEY(food_id) REFERENCES foods(id) ON DELETE CASCADE,
        #     FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        # )
        # """)

        conn.commit()


# ------------- UTILITY FUNCTIONS --------------------------------
def get_formatted_date():
    today = date.today()
    formatted_date = f"{today.month}/{today.day}/{today.year}"
    return formatted_date

def get_menu_url(dining_hall, date_str=None):
    if dining_hall not in DINING_HALL_ID_DICT:
        raise ValueError(f"{dining_hall} is not a valid dining hall.")
    
    if not date_str:
        date = get_formatted_date()
    else:
        date = date_str

    return f"{BASE_URL}?locationNum={DINING_HALL_ID_DICT[dining_hall]}&dtdate={date}"

def is_valid_menu(soup):
    text = soup.find("div", class_="tab-content")
    if not text:
        return False
    return True

def get_meal_id_map(soup):
    tabs = soup.find_all("a", class_="nav-link")
    num_tabs = len(tabs)

    if num_tabs == 3:
        meal_names = ["breakfast", "lunch", "dinner"]
    elif num_tabs == 2:
        meal_names = ["brunch", "dinner"]
    else:
        raise ValueError(f"Unexpected number of meal tabs: {num_tabs}. Only 2 or 3 supported.")

    meal_id_map = {}
    for tab, meal_name in zip(tabs, meal_names):
        panel_id = tab["href"].lstrip("#")  # e.g., "#pane-1" -> "pane-1"
        meal_id_map[meal_name] = panel_id

    return meal_id_map

# ------------- DB HELPERS ---------------------------------------
# gets all existing urls in the master foods table (used to compare )
def get_existing_urls():
    with sqlite3.connect("macro_tracker.db") as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT url FROM foods")
        return {row["url"] for row in cursor.fetchall()}
        
def batch_insert_foods(foods_with_macros, db_path="macro_tracker.db"):
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT OR IGNORE INTO foods (name, url, protein, carbs, fat, calories, serving_size)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            (f["name"], f["url"], f["protein"], f["carbs"], f["fat"], f["calories"], f["serving_size"])
            for f in foods_with_macros
        ])
        conn.commit()

def batch_insert_menus(foods, db_path="macro_tracker.db"):
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT id, url FROM foods")
        url_to_id = {row["url"]: row["id"] for row in cursor.fetchall()}

        menu_entries = [
            (url_to_id[f["url"]], f["dining_hall"], f["station"], f["date"], f["meal"])
            for f in foods
            if f["url"] in url_to_id  # safety guard
        ]

        cursor.executemany("""
            INSERT OR IGNORE INTO menus (food_id, location, station, date, meal_type)
            VALUES (?, ?, ?, ?, ?)
        """, menu_entries)

        return cursor.rowcount
    
def log_scrape_run(menu_date, ran_at, status, foods_found, new_foods, menu_rows):
    with sqlite3.connect("macro_tracker.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO scrape_runs
            (menu_date, ran_at, status, foods_found, new_foods, menu_rows)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            menu_date,
            ran_at,
            status,
            foods_found,
            new_foods,
            menu_rows
        ))
        conn.commit()

# ------------- SCRAPING  ----------------------------------------

def get_all_foods(soup, date, dining_hall):
    foods = []

    meal_id_map = get_meal_id_map(soup)

    for meal_type, div_id in meal_id_map.items():
        container = soup.find(id=div_id)

        if not container:
            print(f"No menu for {meal_type} on {date} at {dining_hall}")
            continue
        
        cards = container.find_all(class_="card")
        for card in cards:
            station_name = card.find('h5', class_="card-title").text.strip()

            for item in card.find_all(class_="menu-item-row"):
                food_item = item.find('a', class_="menu-item-name", href=True)
                if not food_item:
                    print(f"Couldn't find food item")
                    continue
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

                print(f"Scraped {food_name} from {dining_hall}.")
    
    return foods

def fetch_macros_for_new(new_foods):
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_food = {executor.submit(get_macros, f["url"]): f for f in new_foods}
        for future in as_completed(future_to_food):
            f = future_to_food[future]
            try:
                macros = future.result()
                results.append({**f, **macros})
            except Exception as e:
                print(f"Error fetching macros for {f['name']}: {e}")
    return results

def get_macros(url):
    result = requests.get(url)
    soup = BeautifulSoup(result.text, "html.parser")

    # get name
    name = soup.find("h2").text.strip() if soup.find("h2") else None
    # get serving size
    serving_sizes = soup.find_all("div", class_="nutfactsservsize")
    serving_size = serving_sizes[1].text.strip().lower() if len(serving_sizes) > 1 else None 
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

    print(f"Scraped macros for {name}.")
    return {
        "name": name,
        "url": url,
        "serving_size": serving_size or 0.0,
        "protein": protein or 0.0,
        "carbs": carbs or 0.0,
        "fat": fat or 0.0,
        "calories": calories or 0.0
    }


# -------------- MAIN SCRAPER ------------------------------------
def scrape_all_dining_halls(date_str=None):
    if not date_str:
        date_str = get_formatted_date()

    total_foods_found = 0 # foods scraped from menus
    total_new_foods = 0 # unique new foods to be added to "foods" table
    total_menu_rows = 0 # rows to be added to "menus" table 

    for hall in DINING_HALL_ID_DICT:
        url = get_menu_url(hall, date_str)
        soup = BeautifulSoup(requests.get(url).text, "html.parser")
        if not is_valid_menu(soup):
            print(f"Invalid menu for {hall} on {date_str}")
            continue

        print(f"Scraping {hall} menu on {date_str}")
        foods = get_all_foods(soup, date_str, hall)
        total_foods_found += len(foods)

        # Determine which foods are new
        existing_urls = get_existing_urls()
        new_foods = [f for f in foods if f["url"] not in existing_urls]
        total_new_foods += len(new_foods)

        # Fetch macros only for new foods
        foods_with_macros = fetch_macros_for_new(new_foods)

        # Insert new foods and menus
        batch_insert_foods(foods_with_macros)
        total_menu_rows = batch_insert_menus(foods)

    return total_foods_found, total_new_foods, total_menu_rows, date_str

def run_scraper(date_str=None):
    ran_at = datetime.now().isoformat()
    if not date_str:
        date_str = get_formatted_date()

    try:
        total_foods_found, total_new_foods, total_menu_rows, date_str = scrape_all_dining_halls(date_str)
        # Determine status
        if total_foods_found == 0:
            status = "closed"
        else:
            status = "success"
        error_message = None
    except Exception as e:
        status = "failed"
        error_message = str(e)
        total_foods_found = total_new_foods = total_menu_rows = 0
        date_str = get_formatted_date()

    # Log the run
    log_scrape_run(
        menu_date=date_str,
        ran_at=ran_at,
        status=status,
        foods_found=total_foods_found,
        new_foods=total_new_foods,
        menu_rows=total_menu_rows
    )

    if status == "closed":
        print("Dining halls were closed today.")
    elif status == "success":
        print(f"Scraped {total_foods_found} foods, added {total_new_foods} new foods, {total_menu_rows} menu rows.")
    else:
        print(f"Scraper failed: {error_message}")







def get_food_name_by_id(food_id):
    with sqlite3.connect("macro_tracker.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM foods WHERE id = ?", (food_id,))
        result = cursor.fetchone()
        return result[0] if result else None

def get_foods_by_meal(meal_type, date, dining_hall):
    query = """
        SELECT f.id, f.name, f.station, m.protein, m.carbs, m.fat, m.calories
        FROM foods f
        JOIN macros m ON f.id = m.food_id
        WHERE f.meal = ? AND f.date = ? AND f.dining_hall = ?
    """

    with sqlite3.connect("macro_tracker.db") as conn:
        cursor = conn.cursor()
        cursor.execute(query, (meal_type, date, dining_hall))
        results = cursor.fetchall()

    grouped = {}
    for row in results:
        food_id, name, station, protein, carbs, fat, calories = row
        if station not in grouped:
            grouped[station] = []
        grouped[station].append({
            'id': food_id,
            'name': name,
            'protein': protein,
            'carbs': carbs,
            'fat': fat,
            'calories': calories
        })
    
    return grouped



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



if __name__ == "__main__":
    # user = welcome()
    # user_id = user[0]
    # cli_main()
    # insert_foods_and_macros(urls)
    create_tables()
    run_scraper("12/22/2025")




# CLI functions
# def login():
#     while True:
#         username = input("Enter your username: ")
#         user = get_user_by_username(username)
#         if user:
#             email = input("Enter your email: ")
#             if user[2] == email:
#                 print(f"Welcome back {username}")
#                 return user
#             else:
#                 print("Email is not found or not associate with this username. Please try again.")
#         else:
#             print("Username is not found. Please try again.")

# def register():
#     while True:
#         username = input("Create a username: ")
#         if username_exists(username):
#             print(f"The username {username} is already taken.")
#             continue
            
#         email = input("Enter an email: ")
#         if email_exists(email):
#             print(f"The email {email} is already taken.")
#             continue

#         with sqlite3.connect("macro_tracker.db") as conn:
#             cursor = conn.cursor()
#             cursor.execute("INSERT INTO users (username, email) VALUES (?, ?)", (username, email))
#             conn.commit()
#             print(f"User {username} registered successfully.")
#             return username

# def welcome():
#     while True:
#         has_account = input("Do you have an account? (Y/N) ").strip().lower()
#         if has_account == "y":
#             user = login()
#             return user
#         elif has_account == "n":
#             user = register()
#             return user

#         else:
#             print("Invalid input. Please type either Y or N.")

# def cli_log_food(user_id):
#     food_id = int(input("Choose a food to log: ").strip())
#     food_name = get_food_name_by_id(food_id)
#     quantity = float(input("How many servings?: ").strip())
#     date = "5/19/2025" # HARD CODED DATE
#     meal_type = input("When did you eat this food? (breakfast, lunch, dinner): ").strip().lower()
#     was_logged = log_food(user_id, food_id, quantity, date, meal_type) 
#     if was_logged:
#         print(f"{food_name} (x{quantity}) was successfully logged on {date} for {meal_type}.")
#     else:
#         print("Failed to log food.")

# def cli_view_menu():
#     date = "5/19/2025" # HARDCODED DATE
#     dining_hall = "South Campus" # HARDCODED DINING HALL

#     while True:
#         meal_type = input("Which menu time? (breakfast, lunch, dinner): ").strip().lower()

#         if meal_type == 'breakfast' or meal_type == 'lunch' or meal_type == 'dinner':
#             for food_id, food_name in get_foods_by_meal(meal_type, date, dining_hall):
#                 print(f"{food_id}) {food_name}")
#             break
#         else:
#             print("Invalid meal type. Please try again.")

# def cli_set_macro_goals(user_id):
#     while True:
#         try:
#             calories_goal = float(input("What is your calories goal? ").strip())
#             protein_goal = float(input("What is your protein goal? ").strip())
#             carbs_goal = float(input("What is your carbs goal? ").strip())
#             fat_goal = float(input("What is your fat goal? ").strip())
#         except ValueError:
#             print("Please enter valid numbers.")
#             continue
        
#         was_set = set_macro_goals(user_id, calories_goal, protein_goal, carbs_goal, fat_goal)
#         if was_set:
#             print(f"Macro goals successfully set to: {calories_goal} calories, {protein_goal}g protein, {carbs_goal}g carbs, {fat_goal}g fat.")
#             break
#         else:
#             print("Failed to set macro goals.")

# def cli_view_daily_macros(user_id):
#     date = "5/19/2025" # HARDCODED DATE
#     total = get_daily_macros(user_id, date, False)
#     print(f"You have eaten {total["calories"]} calories, {total["protein"]}g protein, {total["carbs"]}g carbs, and {total["fat"]}g fat.")

# def cli_view_remaining_macros(user_id):
#     date = "5/19/2025" # HARDCODED DATE
#     remaining_macros = get_remaining_macros(user_id, date)
#     print(f"Remaining macros: {remaining_macros['calories_remaining']} calories, {remaining_macros['protein_remaining']}g protein, {remaining_macros['carbs_remaining']}g carbs, {remaining_macros['fat_remaining']}g fat.")

# def cli_view_logged_foods(user_id):
#     date = "5/19/2025" #HARDCODED DATE
#     foods, total = get_daily_macros(user_id, date)
#     for food in foods:
#         print(f"Log #{food['log_id']} - {food['meal']} - {food['name']} (x{food['quantity']})")

# def cli_main():
    # while True:
    #     print("\n=== Macro Tracker Menu ===")
    #     print("1. Log a food")
    #     print("2. View menu")
    #     print("3. Set macro goals")
    #     print("4. View macros eaten for today")
    #     print("5. View remaining macros for today")
    #     print("6. View today's logged foods")
    #     print("7. Remove a food from log")
    #     print("8. Quit")

    #     choice = input("Select an option (1-8): ").strip()

    #     if choice == '1':
    #         cli_log_food(user_id)
    #     elif choice == '2':
    #         cli_view_menu()
    #     elif choice == '3':
    #         cli_set_macro_goals(user_id)
    #     elif choice == '4':
    #         cli_view_daily_macros(user_id)
    #     elif choice == '5':
    #         cli_view_remaining_macros(user_id)
    #     elif choice == '6':
    #         cli_view_logged_foods(user_id)
    #     elif choice == '7':
    #         id = input("Which food would you like to remove? (id): ")
    #         food_name = get_food_name_by_id(id)
    #         was_removed = remove_log_by_id(id)
    #         if was_removed:
    #             print(f"{food_name} was successfully removed from the log.")
    #         else:
    #             print("Failed to remove the food log.")
    #     elif choice == '8':
    #         print("User chose to quit")
    #         break
    #     else:
    #         print("Invalid input.")