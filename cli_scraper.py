# *** OLD ***


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