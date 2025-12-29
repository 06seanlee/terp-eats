# TerpEats

Hello, this is TerpEats, a (currently incomplete) project made by a University of Maryland student trying to track macros at UMD dining halls. This is made in mind for all students at UMD who are trying to track calories and macros, whether for bulking, fighting the Freshman 15, or for the curious. TerpEats allows users to browse what foods are currently available at the dining hall (based on data from nutrition.umd.edu), log foods onto their account from all 3 UMD dining halls, and track how much they ate (calories, protein, carbs, fat). 

## Demo
(todo: insert YT link)

## Features
- Daily scraping for up-to-date menus and specific food information
- User-friendly web interface (inspired by nutrition.umd.edu layout)
- User login and authentication w/ calorie goals and progress checks

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

## Setup / Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/06seanlee/terp-eats.git

2. Navigate into the project directory:
   ```bash
    cd terpeats

3. Install dependencies:
   ```bash
    pip install -r requirements.txt

4. Run the application:
    ```bash
    python app.py

5. Open your browser and go to:
    http://127.0.0.1:5000
