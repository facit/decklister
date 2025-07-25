import sys
from decklister.deck_image_generator import DeckImageGenerator
from decklister.config import Config

def main():
    # Example: parse args, load config, run generator
    deck_file = sys.argv[1] if len(sys.argv) > 1 else None
    config_file = sys.argv[2] if len(sys.argv) > 2 else None
    config = Config.from_file(config_file)
    generator = DeckImageGenerator(config=config, blur_count_area=False)
    generator.run(deck_file)

if __name__ == "__main__":
    main()