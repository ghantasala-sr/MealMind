# 🍽️ Meal Mind - AI-Powered Nutrition Intelligence 

Meal Mind is a comprehensive Streamlit application designed to be your personalized meal planning assistant. Powered by AI and USDA nutrition data, it helps you manage your diet, plan meals, track inventory, and generate shopping lists tailored to your specific nutritional needs and goals.

## 🌟 Key Features (Still under building phase)

*   **Personalized Nutrition Planning**: Calculates your daily caloric and macronutrient needs based on your age, gender, weight, height, activity level, and goals (Weight Loss, Maintenance, Muscle Gain).
*   **AI-Driven Meal Generation**: Generates 7-day meal plans that fit your calculated nutritional profile.
*   **Smart Shopping List**: Automatically creates a consolidated shopping list based on your generated meal plan.
*   **Pantry Inventory Management**: Keep track of what you have at home to avoid overbuying and reduce food waste.
*   **Recipe Suggestions**: Get intelligent recipe suggestions based on ingredients you already have in your inventory.
*   **User Profiles**: Secure login and profile management to save your data and preferences.
*   **Dashboard**: A visual overview of your current stats, meal plan summary, and nutrition targets.

## 🛠️ Tech Stack

*   **Frontend**: [Streamlit](https://streamlit.io/) - For a responsive and interactive web interface.
*   **Backend Logic**: Python
*   **Database**: Snowflake (via `utils/db.py`) - For storing user data, meal plans, and inventory.
*   **API**: [RapidAPI Nutrition Calculator](https://rapidapi.com/blog/directory/nutrition-calculator/) - For fetching accurate DRI (Dietary Reference Intake) values.
*   **Authentication**: Custom secure authentication flow.

## 📂 Project Structure

```
meal_mind_streamlit/
├── Home.py                 # Main entry point of the application
├── .env                    # Environment variables (API keys)
├── utils/                  # Utility functions
│   ├── api.py              # API integration for nutrition data
│   ├── auth.py             # User authentication logic
│   ├── db.py               # Database connection and queries
│   ├── helpers.py          # Helper functions
│   ├── onboarding.py       # Profile setup wizard
│   └── ui.py               # Custom CSS and UI components
└── views/                  # Application pages/views
    ├── dashboard.py        # Main user dashboard
    ├── inventory.py        # Pantry inventory management
    ├── meal_plan.py        # Meal plan generation and display
    ├── profile.py          # User profile settings
    ├── shopping_list.py    # Automated shopping list
    └── suggestions.py      # Recipe suggestions
```

## 🚀 Getting Started

### Prerequisites

*   Python 3.8 or higher
*   A RapidAPI account (to get an API key for the Nutrition Calculator)

### Installation

1.  **Clone the repository** (if you haven't already):
    ```bash
    git clone https://github.com/ghantasala-sr/MealMind.git
    cd MealMind/meal_mind_streamlit
    ```

2.  **Create a virtual environment** (recommended):
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install streamlit requests pandas python-dotenv
    ```

4.  **Set up Environment Variables**:
    Create a `.env` file in the `meal_mind_streamlit` directory and add your RapidAPI & Snowflake credentials:
    ```env
    RAPIDAPI_KEY=your_rapidapi_key_here
    RAPIDAPI_HOST=nutrition-calculator.p.rapidapi.com
    SNOWFLAKE_USER= your_data
    SNOWFLAKE_USERNAME= your_data
    SNOWFLAKE_ACCOUNT= your_data
    SNOWFLAKE_PASSWORD= your_data
    SNOWFLAKE_WAREHOUSE= your_data
    SNOWFLAKE_DATABASE= your_data
    SNOWFLAKE_SCHEMA= your_data
    SNOWFLAKE_ROLE= your_data
    ```

### Running the App

Run the Streamlit application:

```bash
streamlit run Home.py
```

The app will open in your default web browser at `http://localhost:8501`.

## 📖 Usage Guide

1.  **Sign Up**: Create a new account with a username and password.
2.  **Profile Setup**: Complete the onboarding wizard to input your physical details and fitness goals.
3.  **Generate Meal Plan**: Go to the **Meal Plan** tab and click "Generate New Plan" to get a customized weekly menu.
4.  **Shop**: Check the **Shopping List** tab for a list of ingredients needed for your plan.
5.  **Manage Inventory**: Add items you already have to the **Inventory** tab to track your pantry.
6.  **Get Suggestions**: Visit **Suggestions** to find recipes you can make with your current inventory.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

[MIT License](LICENSE)
