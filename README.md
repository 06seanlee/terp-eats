# TerpEats


## Overview
Hello, this is TerpEats, a (currently incomplete) project made by a University of Maryland student trying to watch what they're eating at the dining halls...

This is made in mind for all students at UMD who are trying to track calories, macros, and meals at all 3 of UMD's dining halls, whether for bulking, fighting the Freshman 15, or for anyone curious about what they're putting in their body.

## Demo
Click below to see a (work in progress) demo!

[![Watch Demo](images/terp_eats_thumbnail.png)](https://youtu.be/pOZzLdyp1IY)

## Features
- Daily scraping for up-to-date menus and specific food information from all 3 dining halls
- User-friendly web interface (inspired by nutrition.umd.edu layout)
- User login and authentication w/ food logging, macro goals, and progress checks

## Tech Stack
- **Frontend:** HTML, CSS, JavaScript
- **Backend:** Python (Flask), BeautifulSoup4 (for webscraping)
- **Database:** SQLite
  
## Future Improvements (To-Do List)
- Improved UI
- View food logs over time (progress bars)
- Search feature for food menus
- Sort by macros (e.g. highest protein per calorie ratio)
- Automatic webscraping script
- Deploy publicly!
- Food recommendation logic
- Increased scraping efficiency
- Allergens/Restrictions Labels

## Setup / Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/06seanlee/terp-eats.git

2. Navigate into the project directory:
   ```bash
    cd terp_eats

3. Install dependencies:
   ```bash
    pip install -r requirements.txt

4. Create a .env file and create a variable:
   ```bash
    FLASK_SECRET_KEY = 'your-secret-key'

5. Run the application:
   ```bash
   python app.py

6. Open your browser and go to:
   ```bash
   http://127.0.0.1:5000
