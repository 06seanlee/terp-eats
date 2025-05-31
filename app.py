from flask import Flask, render_template, redirect, session, request, url_for
from werkzeug.security import generate_password_hash, check_password_hash

import scraper

app = Flask(__name__)
app.secret_key = "secret_key" # hardcoded, change later

@app.route('/')
def home():
    # session.clear() # requires log in everytime. REMOVE LATER
    return render_template('index.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        valid_account = scraper.validate_account(username, email, password)

        if valid_account:
            user_id = scraper.get_user_by_username(username)[0]
            session['user_id'] = user_id
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        plain_password = request.form['password']
        hashed_password = generate_password_hash(plain_password)

        user_id = scraper.add_user(username, email, hashed_password)
        return redirect(url_for('login')) if user_id else "Username taken."
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return render_template(url_for('login'))
    
    user_id = session['user_id']
    user = scraper.get_user_by_id(user_id)
    username = user[1]
    macro_goals = scraper.get_macro_goals(user_id)
    daily_macros = scraper.get_daily_macros(user_id, "5/19/2025") # HARD CODED DATE
    remaining_macros = scraper.get_remaining_macros(user_id, "5/19/2025") # HARD CODED DATE
    
    return render_template('dashboard.html', username=username, macro_goals=macro_goals, daily_macros=daily_macros, remaining_macros=remaining_macros)

@app.route('/choose_meal', methods=['GET','POST'])
def choose_meal():
    if 'user_id' not in session:
        return render_template(url_for('login'))
    
    if request.method == 'POST':
        meal = request.form['meal']
        return redirect(url_for('select_foods', meal=meal))

    return render_template('choose_meal.html')

@app.route('/select_foods/<meal>', methods=['GET','POST'])
def select_foods(meal):
    if 'user_id' not in session:
        return redirect(url_for('login'))
     
    if request.method == 'POST':
        selected_foods = request.form.getlist('food_id')
        user_id = session['user_id']

        for food in selected_foods:
            quantity = request.form.get(f'quantity_{food}', type=int)
            if quantity and quantity > 0:
                scraper.log_food(user_id, food, quantity, "5/19/2025", meal) # HARD CODED DATE, CHANGE LATER AND QUANTITY CHANGE
        
        return redirect(url_for('dashboard'))

    foods = scraper.get_foods_by_meal(meal, "5/19/2025", "South Campus") # HARD CODED, CHANGE LATER

    return render_template('select_foods.html', meal=meal, foods=foods)
         
@app.route('/set_goals', methods=['GET','POST'])
def set_goals():
    if request.method == 'POST':
        calorie_goal = request.form['calorie_goal']
        protein_goal = request.form['protein_goal']
        carb_goal = request.form['carb_goal']
        fat_goal = request.form['fat_goal']
        user_id = session['user_id']

        success = scraper.set_macro_goals(user_id, calorie_goal, protein_goal, carb_goal, fat_goal)
        if success:
            return redirect(url_for('dashboard'))
        else:
            return render_template('set_goals.html')
        
    return render_template('set_goals.html')

@app.route('/view_logs', methods=['GET','POST'])
def view_logs():
    user_id = session['user_id']
    date = "5/19/2025" # HARD CODED DATE

    food_logs, total = scraper.get_daily_macros(user_id, date)
    return render_template('view_logs.html', food_logs=food_logs, date=date)

@app.route('/modify_log', methods=['POST'])
def modify_log():
    log_id = request.form['log_id']
    action = request.form['action']
    date = "5/19/2025" # HARD CODED DATE

    if action == 'delete':
        scraper.remove_log_by_id(log_id)
    elif action == 'update':
        quantity = float(request.form['quantity'])
        meal = request.form['meal']
        scraper.update_log(log_id, quantity, date, meal)

    return redirect(url_for('view_logs'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)