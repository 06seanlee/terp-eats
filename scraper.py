from bs4 import BeautifulSoup
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
import requests

# scraper.py used for retrieving nutrition info from website and updating 'foods' and 'menus' table.

BASE_URL = "https://nutrition.umd.edu/"
DINING_HALL_ID_DICT = {
    "South Campus": 16,
    "Yahentamitsi Dining Hall": 19,
    "251 North": 51
}


# creates sqlite db (one time use) (DOESN'T HAVE MACRO_GOALS, AND LOGS YET)
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

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS food_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            visitor_id TEXT,
            food_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            meal_type TEXT NOT NULL,
            servings REAL DEFAULT 1.0,
            FOREIGN KEY(food_id) REFERENCES foods(id) ON DELETE CASCADE,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
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

if __name__ == "__main__":
    create_tables()
    run_scraper("12/23/2025")
