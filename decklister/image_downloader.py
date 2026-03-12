import os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed


CDN_BASE = "https://swudb.com/images/cards"
MAX_WORKERS = 8  # Number of concurrent downloads


def download_images(card_set, card_number=None):
    """
    Downloads card images using the swu-db.com API.

    Args:
        card_set (str): The card set identifier (e.g., 'SOR', 'SHD').
        card_number (str or int, optional): If provided, only this card is downloaded.
            Otherwise, downloads all cards in the set sequentially.
    """
    if not card_set:
        print("No card set specified.")
        return

    output_dir = os.path.join("images", card_set)
    os.makedirs(output_dir, exist_ok=True)

    if card_number is not None:
        download_card(card_set, card_number, output_dir)
    else:
        # Download all cards in sequence until we get a 404
        i = 1
        while True:
            result = download_card(card_set, i, output_dir)
            if result == -1:
                break
            i += 1


def download_images_batch(cards):
    """
    Download images for a list of (card_set, card_number) tuples concurrently.

    Args:
        cards: List of (card_set, card_number) tuples.
    """
    # Deduplicate and prepare output dirs
    unique_cards = list(set(cards))
    for card_set, _ in unique_cards:
        os.makedirs(os.path.join("images", card_set), exist_ok=True)

    # Filter out already-downloaded cards
    to_download = []
    for card_set, card_number in unique_cards:
        num_str = str(card_number).zfill(3) if str(card_number).isdigit() else str(card_number)
        filepath = os.path.join("images", card_set, f"{num_str}.png")
        if not os.path.isfile(filepath):
            to_download.append((card_set, card_number))

    if not to_download:
        return

    print(f"Downloading {len(to_download)} card image(s)...")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(download_card, card_set, card_number, os.path.join("images", card_set)): (card_set, card_number)
            for card_set, card_number in to_download
        }
        for future in as_completed(futures):
            card_set, card_number = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"Error downloading {card_set} #{card_number}: {e}")


def download_card(card_set, card_number, output_dir):
    """
    Download a single card image via the API.

    Args:
        card_set (str): The card set identifier.
        card_number (str or int): The card number.
        output_dir (str): Directory to save the image.

    Returns:
        1 if downloaded, 0 if already exists, -1 if not found.
    """
    card_number = str(card_number)
    # Pad to 3 digits for the filename
    num_str = card_number.zfill(3) if card_number.isdigit() else card_number
    filename = f"{num_str}.png"
    filepath = os.path.join(output_dir, filename)

    if os.path.isfile(filepath):
        return 0

    url = f"{CDN_BASE}/{card_set}/{num_str}.png"
    print(f"Downloading {card_set} #{num_str}...")

    try:
        response = requests.get(url, allow_redirects=True, timeout=15)
        response.raise_for_status()

        with open(filepath, "wb") as f:
            f.write(response.content)

        return 1

    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            return -1
        print(f"HTTP error downloading {card_set} #{num_str}: {e}")
        return -1

    except Exception as e:
        print(f"Failed to download {card_set} #{num_str}: {e}")
        return -1


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python image_downloader.py <card_set> [<card_number>]")
        sys.exit(1)

    card_set = sys.argv[1]
    card_number = sys.argv[2] if len(sys.argv) > 2 else None

    download_images(card_set, card_number)
