"""Utility functions for BedrockV2V extension."""
from io import BytesIO
from PIL import Image
from typing import List, Tuple, Any

def is_punctuation(char: str) -> bool:
    """Check if a character is a punctuation mark."""
    return char in [",", "，", ".", "。", "?", "？", "!", "！"]

def parse_sentence(sentence: str, content: str) -> Tuple[str, str, bool]:
    """Parse a sentence and return the complete sentence, remaining content, and completion status."""
    remain = ""
    found_punc = False

    for char in content:
        if not found_punc:
            sentence += char
        else:
            remain += char

        if not found_punc and is_punctuation(char):
            found_punc = True

    return sentence, remain, found_punc

def rgb2base64jpeg(rgb_data: bytes, width: int, height: int) -> bytes:
    """Convert RGB data to JPEG format."""
    # Convert the RGB image to a PIL Image
    pil_image = Image.frombytes("RGBA", (width, height), bytes(rgb_data))
    pil_image = pil_image.convert("RGB")

    # Resize the image while maintaining its aspect ratio
    pil_image = resize_image_keep_aspect(pil_image, 640)

    # Save the image to a BytesIO object in JPEG format
    buffered = BytesIO()
    pil_image.save(buffered, format="JPEG")
    
    return buffered.getvalue()

def resize_image_keep_aspect(image: Image.Image, max_size: int = 512) -> Image.Image:
    """Resize an image while maintaining its aspect ratio."""
    width, height = image.size

    if width <= max_size and height <= max_size:
        return image

    aspect_ratio = width / height

    if width > height:
        new_width = max_size
        new_height = int(max_size / aspect_ratio)
    else:
        new_height = max_size
        new_width = int(max_size * aspect_ratio)

    return image.resize((new_width, new_height))

def filter_images(image_array: List[Any], max_images: int = 10) -> List[Any]:
    """Filter images to maintain a maximum count while preserving temporal distribution."""
    if len(image_array) <= max_images:
        return image_array
    
    result = []
    skip = len(image_array) // max_images
    
    for i in range(0, len(image_array), skip):
        result.append(image_array[i])
        if len(result) == max_images:
            break
    
    return result

# merge images into one image with a grid layout
def merge_images(image_array: List[Any], max_images: int = 4, width: int = 512) -> bytes:
    """Merge multiple images into one image."""
    if len(image_array) == 0:
        return b""
    if len(image_array) > max_images:
        # Filter images to maintain a maximum count while preserving temporal distribution
        image_array = filter_images(image_array, max_images)
    
    total_images = len(image_array)
    # Calculate the number of rows and columns for the grid
    rows = int((total_images - 1) / 2) + 1
    cols = 2 if total_images > 1 else 1

    # Calculate the size of each image in the grid
    image_width = width // cols
    image_height = image_width

    # Create a new image to store the grid
    grid = Image.new("RGB", (width, image_height * rows))

    # Paste each image into the grid
    for i, image in enumerate(image_array):
        row = i // cols
        col = i % cols
        image = Image.open(BytesIO(image))
        image = resize_image_keep_aspect(image, image_width)
        grid.paste(image, (col * image_width, row * image_height))

    # Save the grid to a BytesIO object in JPEG format
    buffered = BytesIO()
    grid.save(buffered, format="JPEG")
    
    return buffered.getvalue()
   

def get_greeting_text(language: str) -> str:
    """Get appropriate greeting text based on language."""
    greetings = {
        "zh-CN": "你好。",
        "ja-JP": "こんにちは",
        "ko-KR": "안녕하세요",
        "en-US": "Hi, there."
    }
    return greetings.get(language, "Hi, there.")
