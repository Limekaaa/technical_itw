from PIL import Image, ExifTags
from datetime import datetime
from pathlib import Path
from src.utils.date_handler import standardize_date, DATE_FORMAT, _resolve_bounds, _matches
import logging
import os
import base64
import json

from dotenv import load_dotenv
from google import genai

load_dotenv()

client =genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

MODEL_NAME = "gemini-3.5-flash-lite"
MACRO_SCHEMA = {
    "type": "object",
    "properties": {
        "calories": {"type": "integer"},
        "protein": {"type": "integer"},
        "carbohydrates": {"type": "integer"},
        "fats": {"type": "integer"},
    },
    "required": ["calories", "protein", "carbohydrates", "fats"],
}
MACRO_RESPONSE_FORMAT = {
    "type": "text",
    "mime_type": "application/json",
    "schema": MACRO_SCHEMA,
}
_BASE_DIR = Path(__file__).resolve().parents[2]
_DATA_DIR = _BASE_DIR / "data"


def _image_part(file_path: str, image_bytes: bytes) -> dict:
    """Build a doc-shaped multimodal image part for interactions.create."""
    suffix = Path(file_path).suffix.lower()
    mime_type = "image/png" if suffix == ".png" else "image/jpeg"
    return {
        "type": "image",
        "data": base64.b64encode(image_bytes).decode("utf-8"),
        "mime_type": mime_type,
    }

def _read_image_metadata(image_path: str) -> dict:
    """Read metadata from an image file."""
    try:
        with Image.open(image_path) as img:
            exif_raw = img._getexif()
            if not exif_raw:
                return {}
            exif = { ExifTags.TAGS[k]: v for k, v in exif_raw.items() if k in ExifTags.TAGS }
            if exif:
                return {ExifTags.TAGS.get(k, k): v for k, v in exif.items()}
            return {}
    except Exception as e:
        logging.warning(f"Error reading image metadata: {e}")
        return {}

def photo_selector_by_date_player(player_id: str, start_date: str, end_date=None) -> list:
    """Select photos from a player within a date range."""
    lower, upper, upper_inclusive = _resolve_bounds(start_date, end_date)
    path = _DATA_DIR / player_id / "food-images"
    if not path.is_dir():
        return []

    selected_file_paths = []

    for image_file in [os.path.join(path, f) for f in os.listdir(path) if f.endswith(('.jpg', '.jpeg', '.png'))]:
        img_date = standardize_date(_read_image_metadata(image_file).get("DateTime", ""))
        if not img_date:
            logging.warning(f"No date info for image, skipping: {image_file}")
            continue
        if _matches(img_date, lower, upper, upper_inclusive):
            selected_file_paths.append(image_file)

    return selected_file_paths

def is_photo_food(file_path: str) -> bool:
    """Determine if a photo is of food using Gemini."""
    try:
        with open(file_path, "rb") as f:
            image_bytes = f.read()
        prompt = f"Is this a photo of food or beverages meant for human consumption? " + "Answer strictly 'YES' or 'NO'."
        response = client.interactions.create(
            model=MODEL_NAME,
            input=[
                {"type": "text", "text": prompt},
                _image_part(file_path, image_bytes),
            ],
        )
        answer = response.output_text.strip().lower()
        if not answer.startswith("yes") and not answer.startswith("no"):
            raise ValueError(f"Unexpected response from Gemini: {answer}")
        return answer.startswith("yes")
    except Exception as e:
        logging.warning(f"Error determining if photo is food: {e}")
        return False

def _parse_photo_date(value):
    """Parse a (path, date) tuple date back to datetime.

    Dates are produced by standardize_date, so they are parsed with
    DATE_FORMAT, the same format standardize_date emits.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.strptime(value, DATE_FORMAT)


def _dated_files(files: list) -> list:
    """Keep (path, datetime) pairs, warning and skipping dateless entries."""
    dated = []
    for path, date in files:
        dt = _parse_photo_date(date)
        if dt is None:
            logging.warning(f"No date info for photo, skipping: {path}")
            continue
        dated.append((path, dt))
    return dated


def same_meal_preselector(files: list, meal_timedelta: int = 1800) -> dict:
    """Preselect photos that are likely to be of the same meal based on time difference.

    Args:
        files (list): List of (path, date) tuples. Dates are standardized
            date strings (as produced by standardize_date) or datetimes.
        meal_timedelta (int): Time difference threshold in seconds.
    Returns:
        dict: Symmetric adjacency {path: [paths within threshold]}.
    """
    dated = _dated_files(files)
    possible_same_meal = {path: [] for path, _ in dated}
    for i in range(len(dated)):
        for j in range(i + 1, len(dated)):
            if abs((dated[i][1] - dated[j][1]).total_seconds()) <= meal_timedelta:
                possible_same_meal[dated[i][0]].append(dated[j][0])
                possible_same_meal[dated[j][0]].append(dated[i][0])
    return possible_same_meal




def is_it_same_meal(file_path_date_1: tuple, file_path_date_2: tuple) -> bool:
    """Determine if two photos are of the same meal."""
    try:
        with open(file_path_date_1[0], "rb") as f1, open(file_path_date_2[0], "rb") as f2:
            image_bytes1 = f1.read()
            image_bytes2 = f2.read()
        prompt = f"Look at these two photos. Photo 1 has been taken on {file_path_date_1[1]}. Photo 2 has been taken on {file_path_date_2[1]}. Do they depict the same meal event? " + \
            "They might be different angles, slightly different plates from the same sitting, " + \
            "or a 'before and during' eating comparison. " + \
            "Answer strictly 'YES' or 'NO'."
        response = client.interactions.create(
            model=MODEL_NAME,
            input=[
                {"type": "text", "text": prompt},
                _image_part(file_path_date_1[0], image_bytes1),
                _image_part(file_path_date_2[0], image_bytes2),
            ],
        )
        answer = response.output_text.strip().lower()
        if not answer.startswith("yes") and not answer.startswith("no"):
            raise ValueError(f"Unexpected response from Gemini: {answer}")
        return answer.startswith("yes")
    except Exception as e:
        logging.warning(f"Error determining if photos are of the same meal: {e}")
        return False

def helper_get_macro_nutrients_from_photos(files_paths: list) -> dict:
    """Use <model> to extract macro-nutrients from photo metadata.
    Args:
        file_path (str): File path to the photos.
    Returns:
        dict: A dictionary with macro-nutrient information.
    """
    try:
        parts = []
        for file_path in files_paths:
            with open(file_path, "rb") as f:
                parts.append(_image_part(file_path, f.read()))
        prompt = "Analyze these photos. They are all of the same meal event. " + \
            "Estimate the total calories, protein (in grams), " + \
            "carbohydrates (in grams), and fats (in grams)."
        interaction = client.interactions.create(
            model=MODEL_NAME,
            input=[
                {"type": "text", "text": prompt},
                *parts,
            ],
            response_format=MACRO_RESPONSE_FORMAT,
        )
        return json.loads(interaction.output_text.strip())
    except Exception as e:
        logging.warning(f"Error extracting macro-nutrients from photos: {e}")
        return {}

    

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

    dated = _dated_files(files)
    parent = list(range(len(dated)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(dated)):
        for j in range(i + 1, len(dated)):
            if abs((dated[i][1] - dated[j][1]).total_seconds()) <= meal_timedelta:
                if is_it_same_meal(dated[i], dated[j]):
                    ri, rj = find(i), find(j)
                    if ri != rj:
                        parent[max(ri, rj)] = min(ri, rj)
    groups = {}
    for i, (path, _) in enumerate(dated):
        groups.setdefault(find(i), []).append(path)
    meals = list(groups.values())

    for meal in meals:
        #if len(meal) == 1:
        #    meal_file_path = meal[0]
        macro_nutrients[tuple(meal)] = helper_get_macro_nutrients_from_photos(meal)
        """
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
                tmp_macro_nutrients = helper_get_macro_nutrients_from_photos([meal_file_path])
                for key in full_meal_macro_nutrients:
                    full_meal_macro_nutrients[key] += tmp_macro_nutrients.get(key, 0)

            for key in full_meal_macro_nutrients:
                full_meal_macro_nutrients[key] /= len(meal)
            macro_nutrients[tuple(meal)] = full_meal_macro_nutrients
        """
                
    return macro_nutrients
