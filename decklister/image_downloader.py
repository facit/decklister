import os
import time
import requests
from PIL import Image  # Requires Pillow: pip install pillow

def download_images(card_set, card_number=None):
    """
    Downloads images for the specified card set.
    The images are expected to be named in the format [number].png and [number]-portrait.png or [number]-back.png.

    Args:
        card_set (str): The card set identifier (used in the URL and output directory).
        card_number (int, optional): If provided, only this card number is downloaded. Otherwise, downloads all sequentially.
    """
    if not card_set:
        print("No card set specified.")
        return

    # Base URL for image downloads
    base_url = "https://swudb.com/images/cards/" + card_set + "/"

    # HTTP headers to mimic a browser request
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/115.0.0.0 Safari/537.36")
    }

    # Output directory for downloaded images
    output_dir = os.path.join("images", card_set)
    os.makedirs(output_dir, exist_ok=True)

    delay_seconds = 0.25  # Delay between downloads to avoid hammering the server

    if card_number is not None:
        # Download a single card if card_number is specified
        ret = download_image(card_number, base_url, headers, output_dir)
        if ret == -1:
            print(f"Failed to download image for card number {card_number}.")
    else:
        # Download all cards in sequence until a card is missing (download_image returns -1)
        i = 1
        while(True):
            ret = download_image(i, base_url, headers, output_dir)
            if ret == -1:
                break  # Stop when no more images are found
            elif ret == 0:
                i += 1
                continue  # Skip already-downloaded images

            time.sleep(delay_seconds)
            i += 1

def download_image(card_number, base_url, headers, output_dir):
    """
    Downloads the main image for a card, and attempts to download its portrait or back image.
    Handles renaming and swapping based on image orientation.

    Args:
        card_number (int): The card number to download.
        base_url (str): The base URL for image downloads.
        headers (dict): HTTP headers for the request.
        output_dir (str): Directory to save images.

    Returns:
        int: 1 if image downloaded, 0 if already exists, -1 if failed.
    """
    card_number = int(card_number)
    num_str = f"{card_number:03d}"  # Pad card number to 3 digits
    main_filename = f"{num_str}.png"
    main_url = f"{base_url}{main_filename}"
    
    full_filename = os.path.join(output_dir, main_filename)
    if os.path.isfile(full_filename):
        # Image already exists, skip downloading
        return 0
    print(f"Fetching {main_url}...")
    try:
        response = requests.get(main_url, headers=headers)
        response.raise_for_status()
        with open(full_filename, "wb") as f:
            f.write(response.content)
    except Exception as e:
        # Download failed, return -1 to signal end of sequence
        # print(f"Failed to fetch {main_url}: {e}")
        return -1

    # Check if the downloaded image is landscape (width > height)
    with Image.open(full_filename) as img:
        width, height = img.size
        if width > height:
            # Try to download the portrait version of the card
            portrait_filename = f"{num_str}-portrait.png"
            portrait_url = f"{base_url}{portrait_filename}"
            try:
                print(f"Trying portrait image: {portrait_url}...")
                response = requests.get(portrait_url, headers=headers)
                response.raise_for_status()
                with open(os.path.join(output_dir, portrait_filename), "wb") as f:
                    f.write(response.content)
            except Exception as e:
                # If portrait image is not available, try the back image
                print(f"Portrait not available for {num_str} (error: {e}). Trying back image...")
                back_filename = f"{num_str}-back.png"
                back_url = f"{base_url}{back_filename}"
                try:
                    response = requests.get(back_url, headers=headers)
                    response.raise_for_status()
                    with open(os.path.join(output_dir, back_filename), "wb") as f:
                        f.write(response.content)
                    
                    # Check orientation of the back image
                    back_image_path = os.path.join(output_dir, back_filename)
                    with Image.open(back_image_path) as img:
                        width, height = img.size
                    
                    if height > width:
                        # If back image is portrait, rename it to portrait
                        os.rename(back_image_path, os.path.join(output_dir, portrait_filename))
                        print(f"Renamed {back_filename} to {portrait_filename} for {num_str} (portrait)")
                    else:
                        # If back image is landscape, swap with main image
                        os.rename(os.path.join(output_dir, main_filename), os.path.join(output_dir, portrait_filename))
                        os.rename(back_image_path, os.path.join(output_dir, main_filename))
                        print(f"Swapped images for {num_str}: main -> {portrait_filename} and back -> {main_filename} (landscape)")
                except Exception as e2:
                    pass # Ignore if back image is also not available
    return 1

if __name__ == "__main__":
    # Entry point for command-line usage
    import sys
    if len(sys.argv) < 2:
        print("Usage: python image_downloader.py <card_set> [<card_number>]")
        sys.exit(1)

    card_set = sys.argv[1]
    card_number = int(sys.argv[2]) if len(sys.argv) > 2 else None

    download_images(card_set, card_number)
