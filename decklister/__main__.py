import sys


def main_cli():
    import argparse

    try:
        from .deck_image_generator import DeckImageGenerator
        from .config import Config
    except ImportError:
        from decklister.deck_image_generator import DeckImageGenerator
        from decklister.config import Config

    parser = argparse.ArgumentParser(description="Generate deck images from a deck file.")
    parser.add_argument("deck_file", help="Path to the deck file")
    parser.add_argument("config_file", help="Path to the config file")
    parser.add_argument("-o", "--output", help="Output file path (auto-named if not provided)", default=None)
    args = parser.parse_args()

    config = Config.from_file(args.config_file)
    generator = DeckImageGenerator(config=config)
    generator.run(args.deck_file, output_path=args.output)


def main_gui():
    try:
        from .gui import main
    except ImportError:
        from decklister.gui import main
    main()


if __name__ == "__main__":
    # If arguments are provided, run CLI. Otherwise, launch GUI.
    if len(sys.argv) > 1:
        main_cli()
    else:
        main_gui()
