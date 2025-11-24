import requests

RAPIDAPI_KEY = "aa03950e0emshbe5be62d4b8a130p10ba64jsn7ada38029b57"
RAPIDAPI_HOST = "nutrition-calculator.p.rapidapi.com"


def get_nutrition_info_from_api(age, gender, height_cm, weight_kg, activity_level, pregnancy, lactation):
    """Get DRI nutrition info from RapidAPI"""
    url = "https://nutrition-calculator.p.rapidapi.com/api/nutrition-info"

    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": RAPIDAPI_HOST
    }

    total_inches = height_cm / 2.54
    feet = int(total_inches // 12)
    inches = int(total_inches % 12)
    lbs = int(weight_kg * 2.20462)

    activity_map = {
        "Sedentary": "Sedentary",
        "Lightly active": "Light",
        "Moderately active": "Moderate",
        "Very active": "Active",
        "Extremely active": "Very Active"
    }

    params = {
        "measurement_units": "std",
        "sex": gender.lower(),
        "age_value": str(age),
        "age_type": "yrs",
        "feet": str(feet),
        "inches": str(inches),
        "lbs": str(lbs),
        "activity_level": activity_map.get(activity_level, "Moderate")
    }

    if pregnancy != "Not Pregnant":
        params["pregnancy_status"] = "pregnant"
        if "1st" in pregnancy:
            params["trimester"] = "1"
        elif "2nd" in pregnancy:
            params["trimester"] = "2"
        elif "3rd" in pregnancy:
            params["trimester"] = "3"

    if lactation != "Not Lactating":
        params["lactation_status"] = "lactating"

    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None


def parse_macro_value(macro_table, nutrient_name):
    """Extract nutrient value from macronutrients table"""
    try:
        for row in macro_table[1:]:
            if row[0] == nutrient_name:
                value_str = row[1]
                if '-' in value_str:
                    first_value = value_str.split('-')[0].strip().split()[0]
                    return float(first_value.replace(',', ''))
                else:
                    value = value_str.split()[0]
                    return float(value.replace(',', ''))
        return 0
    except:
        return 0


def calculate_manual(age, gender, weight, height, activity, goal):
    """Manual calculation as backup"""
    height_m = height / 100
    bmi = round(weight / (height_m ** 2), 1)

    if gender == "Male":
        bmr = 88.362 + (13.397 * weight) + (4.799 * height) - (5.677 * age)
    else:
        bmr = 447.593 + (9.247 * weight) + (3.098 * height) - (4.330 * age)

    multipliers = {
        "Sedentary": 1.2,
        "Lightly active": 1.375,
        "Moderately active": 1.55,
        "Very active": 1.725,
        "Extremely active": 1.9
    }

    calories = int(bmr * multipliers.get(activity, 1.2))

    if goal == "Weight Loss":
        calories -= 500
    elif goal in ["Weight Gain", "Muscle Gain"]:
        calories += 500

    protein = round(weight * 1.6, 1)
    fat = round((calories * 0.25) / 9, 1)
    carbs = round((calories - (protein * 4) - (fat * 9)) / 4, 1)

    return {
        'bmi': bmi,
        'daily_calories': calories,
        'daily_protein': protein,
        'daily_carbohydrate': carbs,
        'daily_fat': fat,
        'daily_fiber': 30
    }


def calculate_nutrition_targets(age, gender, weight, height, activity, goal, pregnancy="Not Pregnant", lactation="Not Lactating"):
    """Calculate nutrition targets using API with manual fallback"""
    
    # Try API first
    api_data = get_nutrition_info_from_api(
        age, gender, height, weight,
        activity, pregnancy, lactation
    )

    if api_data:
        try:
            bmi = api_data.get('BMI_EER', {}).get('BMI', '0')
            calories_str = api_data.get('BMI_EER', {}).get('Estimated Daily Caloric Needs', '2000 kcal/day')
            calories = int(calories_str.replace(',', '').split()[0])
            macro_table = api_data.get('macronutrients_table', {}).get('macronutrients-table', [])

            return {
                'bmi': float(bmi),
                'daily_calories': calories,
                'daily_protein': parse_macro_value(macro_table, 'Protein'),
                'daily_carbohydrate': parse_macro_value(macro_table, 'Carbohydrate'),
                'daily_fat': parse_macro_value(macro_table, 'Fat'),
                'daily_fiber': parse_macro_value(macro_table, 'Total Fiber')
            }
        except Exception as e:
            print(f"Error parsing API data: {e}")
            # Fall through to manual
            pass

    # Fallback to manual
    return calculate_manual(age, gender, weight, height, activity, goal)


def get_bmi_category(bmi):
    """Categorize BMI"""
    try:
        bmi_val = float(bmi) if isinstance(bmi, str) else bmi
        if bmi_val < 18.5:
            return "Underweight", "🔵"
        elif 18.5 <= bmi_val < 25:
            return "Normal Weight", "🟢"
        elif 25 <= bmi_val < 30:
            return "Overweight", "🟡"
        else:
            return "Obese", "🔴"
    except:
        return "Unknown", "⚪"
