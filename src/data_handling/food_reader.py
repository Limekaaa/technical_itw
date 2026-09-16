from PIL import Image, ExifTags
from pathlib import Path
from src.utils.date_handler import standardize_date, _resolve_bounds, _matches
import logging
import os

_BASE_DIR = Path(__file__).resolve().parents[2]

def _read_image_metadata(image_path: str) -> dict:
    """Read metadata from an image file."""
    try:
        with Image.open(image_path) as img:
            exif = { ExifTags.TAGS[k]: v for k, v in img._getexif().items() if k in ExifTags.TAGS }
            if exif:
                return {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
            return {}
    except Exception as e:
        logging.warning(f"Error reading image metadata: {e}")
        return {}

def photo_selector_by_date_player(player_id: str, start_date: str, end_date=None) -> list:
    """Select photos from a player within a date range."""
    lower, upper, upper_inclusive = _resolve_bounds(start_date, end_date)
    path = _BASE_DIR / player_id / "food-images"
    print(path)
    if not path.is_dir():
        return []
    
    selected_file_paths = []
   
    for image_file in [os.path.join(path, f) for f in os.listdir(path) if f.endswith(('.jpg', '.jpeg', '.png'))]:
        img_date = standardize_date(_read_image_metadata(image_file).get("DateTime", ""))
        if img_date and _matches(img_date, lower, upper, upper_inclusive):
            selected_file_paths.append(image_file)

    return selected_file_paths

def is_photo_food(file_path: str) -> bool:
    """Determine if a photo is of food."""
    # model to determine if the photo is about food or not
    return True

def same_meal_preselector(file_paths: list, meal_timedelta: int = 1800) -> dict:
    """Preselect photos that are likely to be of the same meal based on time difference."""
    possible_same_meal = {}
    for i in range(len(file_paths)):
        possible_same_meal[file_paths[i][0]] = []
        for j in range(i + 1, len(file_paths)):
            if file_paths[i][1] and file_paths[j][1] and abs((file_paths[i][1] - file_paths[j][1]).total_seconds()) <= meal_timedelta:
                possible_same_meal[file_paths[i][0]].append(file_paths[j][0])
    return possible_same_meal



def is_it_same_meal(file_path1: str, file_path2: str) -> bool:
    """Determine if two photos are of the same meal."""
    # model to determine if the two photos are of the same meal
    # features are the metadata: time between the two photos, and image? 
    # CV model backbone + post training (triplet loss/contrastive loss)
    return False

def get_macro_nutrients_from_photo(file_path: str) -> dict:
    """Use <model> to extract macro-nutrients from photo metadata.
    Args:
        file_path (str): File path to the photo.
    Returns:
        dict: A dictionary with macro-nutrient information.
    """
    # Use the model to extract macro-nutrients from the photo
    # For now, we will just return dummy values
    return {
        "calories": 0,
        "protein": 0,
        "carbohydrates": 0,
        "fats": 0
    }

def get_macro_nutrients_from_photos(file_paths: list, meal_timedelta:int=1800) -> dict:
    """Use <model> to extract macro-nutrients from photo metadata.
    Args:
        file_paths (list): List of file paths to the photos.
        meal_timedelta (int): Time difference threshold in seconds to consider photos as the same meal.
    Returns:
        dict: A dictionary with file paths as keys and macro-nutrient information as values.
    """
    macro_nutrients = {}
    files = [] # (path, date)
    for file_path in file_paths:
        if is_photo_food(file_path):
            files.append((file_path, standardize_date(_read_image_metadata(file_path).get("DateTime", ""))))

    possible_same_meal = same_meal_preselector(files, meal_timedelta)
    meals = []
    already_grouped = set()
    for key in possible_same_meal:
        meal_group = [key]
        already_grouped.add(key)
        for value in possible_same_meal[key]:
            if is_it_same_meal(key, value):
                if value not in already_grouped:
                    already_grouped.add(value)
                    meal_group.append(value)
        meals.append(meal_group)        

    for meal in meals:
        if len(meal) == 1:
            meal_file_path = meal[0]
            macro_nutrients[meal_file_path] = get_macro_nutrients_from_photo(meal_file_path)
        else:
            # Use the model to extract macro-nutrients from the meal photos
            # For now, we will just return dummy values
            full_meal_macro_nutrients = {
                "calories": 0,
                "protein": 0,
                "carbohydrates": 0,
                "fats": 0
            }
            for meal_file_path in meal:
                tmp_macro_nutrients = get_macro_nutrients_from_photo(meal_file_path)
                for key in full_meal_macro_nutrients:
                    full_meal_macro_nutrients[key] += tmp_macro_nutrients.get(key, 0)

            for key in full_meal_macro_nutrients:
                full_meal_macro_nutrients[key] /= len(meal)
            macro_nutrients[tuple(meal)] = full_meal_macro_nutrients
                
    return macro_nutrients
