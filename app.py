from flask import Flask, render_template, redirect, session, request, url_for
import scraper

app = Flask(__name__)
app.secret_key = "secret_key" # hardcoded, change later

@app.route('/')
def home():
    session.clear() # requires log in everytime. REMOVE LATER
    return redirect(url_for('dashboard')) if 'user_id' in session else redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        valid_account = scraper.validate_account(username, email)

        if valid_account:
            user_id = scraper.get_user_by_username(username)[0]
            print(user_id)
            session['user_id'] = user_id
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))
    return render_template(('login.html'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        user_id = scraper.add_user(username, email)
        return redirect(url_for('login')) if user_id else "Username taken."
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return render_template(url_for('login'))
    
    user_id = session['user_id']
    user = scraper.get_user_by_id(user_id)
    username = user[1]
    
    return render_template('dashboard.html', username=username)

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
            # GET QUANTITY LATER
            scraper.log_food(user_id, food, 1, "5/19/2025", meal) # HARD CODED DATE, CHANGE LATER AND QUANTITY CHANGE
        
        return redirect(url_for('dashboard'))

    foods = scraper.get_foods_by_meal(meal, "5/19/2025", "South Campus") # HARD CODED, CHANGE LATER

    return render_template('select_foods.html', meal=meal, foods=foods)
         


if __name__ == "__main__":
    app.run(debug=True)