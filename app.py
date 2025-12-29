from flask import Flask, render_template, redirect, session, request, url_for
from werkzeug.security import generate_password_hash
import os
from dotenv import load_dotenv
import uuid

import database
import scraper

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY not set")


@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        is_valid_account = database.validate_account(username, password)

        if is_valid_account:
            user_id = database.get_user_by_username(username)[0]
            session['user_id'] = user_id
            return redirect(url_for('menu'))
        return render_template('login.html', attempted=True)
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if not database.validate_password_strength(password):
            return render_template('register.html', bad_password=True)

        user_id = database.create_user(username, email, password)
        if user_id:
            session['user_id'] = user_id
            return redirect(url_for('menu'))
        else:
            return render_template('register.html', attempted=True)
        
    return render_template('register.html')

@app.route("/guest")
def continue_as_guest():
    if "guest_id" not in session:
        session["guest_id"] = str(uuid.uuid4())
    if session.get("dining_hall"):
        return redirect(url_for("menu"))
    return redirect(url_for("menu"))  

@app.route("/menu", methods=["GET", "POST"])
def menu():
    dining_hall = session.get("dining_hall")
    if not dining_hall:
        session["dining_hall"] = "South Campus" # default to south campus dining hall

    current_date = scraper.get_formatted_date() # used for logging, DON'T CHANGE
    if not session.get("date"):
        date = scraper.get_formatted_date() # auto filled date used for displaying (based on current)
    else:
        date = session["date"]


    if request.method == "POST":
        # user wants to change menu
        if request.form.get("change-menu"):
            dining_hall = request.form.get("dining-hall")
            if dining_hall != "Placeholder":
                session["dining_hall"] = dining_hall
                
            new_date = request.form.get('date')
            if new_date: # menu has entries from this date
                date = database.format_date(new_date) # correct formatting for date
                session["date"] = date
            
            return redirect(url_for("menu"))


        selected_food_ids = request.form.getlist("food_id")
        if not selected_food_ids:
            return render_template("menu.html", foods=None, date=date)

        for food_id in selected_food_ids:
            quantity = int(request.form.get(f"quantity_{food_id}", 1))

            if session.get("user_id"):
                meal = request.form.get('meal_type')
                database.log_food(True, session.get("user_id"), food_id, quantity, current_date, meal) # log food using user id
            else:
                meal = request.form.get('meal_type')
                database.log_food(False, session.get("guest_id"), food_id, quantity, current_date, meal) # log food using guest id

        return redirect(url_for("dashboard"))

    has_brunch = database.has_brunch(date)

    foods = {}
    if has_brunch:
        for meal in ['brunch', 'dinner']:
            result = database.get_foods_by_meal(meal, date, dining_hall)
            if result:
                foods[meal] = result 
        print("BRUNCH BRUNCH BRUNCH")
    else:
        for meal in ['breakfast', 'lunch', 'dinner']:
            result = database.get_foods_by_meal(meal, date, dining_hall)
            if result:
                foods[meal] = result 
        print("NOT BRUNCH NOT BRUNCH")

    return render_template(
        "menu.html",
        foods=foods,
        date=date,
        has_brunch=has_brunch
    )

@app.route('/dashboard')
def dashboard():
    date = scraper.get_formatted_date()
    username = None

    if 'user_id' in session:
        id = session.get('user_id')
        user = database.get_user_by_id(id)    
        username = user[1]
        foods, total = database.get_daily_macros(True, id, date, True) 
    else:
        id = session.get('guest_id')
        foods, total = database.get_daily_macros(False, id, date, True) 
        
    return render_template('dashboard.html', daily_total=total, username=username, daily_foods=foods)

@app.route('/view_logs')
def view_logs():
    date = scraper.get_formatted_date()
    username = None

    if 'user_id' in session:
        id = session.get('user_id')
        user = database.get_user_by_id(id)    
        username = user[1]
        foods, total = database.get_daily_macros(True, id, date, True) 
    else:
        id = session.get('guest_id')
        foods, total = database.get_daily_macros(False, id, date, True) 
    return render_template("view_logs.html", date=date, food_logs=foods, username=username)

@app.route('/modify_log', methods=['POST'])
def modify_log():
    log_id = request.form.get('log_id')
    action = request.form.get('action')

    if action == 'delete':
        database.remove_log_by_id(log_id)
    elif action == 'update':
        servings = float(request.form.get('servings'))
        if servings < 0:
            servings = 1
        database.update_log(log_id, servings)

    return redirect(url_for('view_logs'))




# @app.route('/dashboard')
# def dashboard():
#     if 'user_id' not in session:
#         return render_template(url_for('login'))
    
#     user_id = session['user_id']
#     macro_goals = scraper.get_macro_goals(user_id)
#     if not macro_goals:
#         return redirect(url_for('set_goals'))
    
#     date = "5/19/2025" # HARD CODED DATE
#     user_id = session['user_id']
#     user = scraper.get_user_by_id(user_id)
#     username = user[1]
#     macro_goals = scraper.get_macro_goals(user_id)
#     total = scraper.get_daily_macros(user_id, date, False) 
#     remaining_macros = scraper.get_remaining_macros(user_id, date)

#     food_logs, trash = scraper.get_daily_macros(user_id, date)
    
#     return render_template('dashboard.html', username=username, macro_goals=macro_goals, daily_total=total, remaining_macros=remaining_macros, food_logs=food_logs)

# @app.route('/choose_meal', methods=['GET','POST'])
# def choose_meal():
#     if 'user_id' not in session:
#         return render_template(url_for('login'))
    
#     if request.method == 'POST':
#         meal = request.form['meal']
#         return redirect(url_for('select_foods', meal=meal))

#     return render_template('choose_meal.html')

# @app.route('/select_foods/<meal>', methods=['GET','POST'])
# def select_foods(meal):
#     if 'user_id' not in session:
#         return redirect(url_for('login'))
     
#     if request.method == 'POST':
#         selected_foods = request.form.getlist('food_id')
#         user_id = session['user_id']

#         for food in selected_foods:
#             quantity = request.form.get(f'quantity_{food}', type=int)
#             if quantity and quantity > 0:
#                 scraper.log_food(user_id, food, quantity, "5/19/2025", meal) # HARD CODED DATE, CHANGE LATER AND QUANTITY CHANGE
        
#         return redirect(url_for('dashboard'))

#     foods = scraper.get_foods_by_meal(meal, "5/19/2025", "South Campus") # HARD CODED, CHANGE LATER

#     return render_template('select_foods.html', meal=meal, foods=foods)
         
# @app.route('/set_goals', methods=['GET','POST'])
# def set_goals():
#     if request.method == 'POST':
#         calorie_goal = request.form['calorie_goal']
#         protein_goal = request.form['protein_goal']
#         remaining_cals = float(calorie_goal) - (float(protein_goal) * 4)
#         carb_goal = round((remaining_cals * 0.5) / 4, 1)
#         fat_goal = round((remaining_cals * 0.5) / 9, 1)
        
#         user_id = session['user_id']
        

#         success = scraper.set_macro_goals(user_id, calorie_goal, protein_goal, carb_goal, fat_goal)
#         if success:
#             session.pop('new_user', None)
#             return redirect(url_for('dashboard'))
#         else:
#             return render_template('set_goals.html', is_new_user=session.get('new_user', False))
        
#     return render_template('set_goals.html', is_new_user=session.get('new_user', False))

# @app.route('/view_logs', methods=['GET','POST'])
# def view_logs():
#     user_id = session['user_id']
#     date = "5/19/2025" # HARD CODED DATE

#     food_logs, total = scraper.get_daily_macros(user_id, date)
#     return render_template('view_logs.html', food_logs=food_logs, date=date)

# @app.route('/modify_log', methods=['POST'])
# def modify_log():
#     log_id = request.form['log_id']
#     action = request.form['action']
#     date = "5/19/2025" # HARD CODED DATE

#     if action == 'delete':
#         scraper.remove_log_by_id(log_id)
#     elif action == 'update':
#         quantity = float(request.form['quantity'])
#         if (quantity < 0):
#             quantity = 1
#         scraper.update_log(log_id, quantity, date)

#     return redirect(url_for('view_logs'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

if __name__ == "__main__":
    app.run(debug=True)