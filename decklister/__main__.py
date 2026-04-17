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
    parser.add_argument("deck_file", help="Path to the deck file (.json or Melee.gg .csv)")
    parser.add_argument("config_file", help="Path to the config file")
    parser.add_argument("-o", "--output", help="Output file path (auto-named if not provided)", default=None)
    parser.add_argument("--hyperspace", action="store_true", help="Use hyperspace variant art for all cards")
    parser.add_argument("--showcase", action="store_true", help="Use showcase variant art for leaders (overrides hyperspace for leaders)")
    parser.add_argument("--player", default=None, help="(CSV only) Player name to select from a multi-deck CSV export")
    parser.add_argument("--index", type=int, default=0, help="(CSV only) 0-based deck index to select from a multi-deck CSV export (default: 0)")
    parser.add_argument("--all", action="store_true", help="(CSV only) Generate images for all decks in the CSV")
    args = parser.parse_args()

    config = Config.from_file(args.config_file)
    generator = DeckImageGenerator(config=config, hyperspace=args.hyperspace, showcase=args.showcase)
    if args.all:
        generator.run_all(args.deck_file, output_path=args.output)
    else:
        generator.run(args.deck_file, output_path=args.output, player=args.player, deck_index=args.index)


def main_gui():
    try:
        from .gui import main
    except ImportError:
        from decklister.gui import main
    main()


if __name__ == "__main__":
    import os

    # Detect whether this is the CLI exe (e.g., DeckLister-cli.exe)
    exe_name = os.path.basename(sys.argv[0]).lower()
    is_cli_exe = "-cli" in exe_name or "_cli" in exe_name

    if is_cli_exe:
        # CLI exe: always run CLI mode. If no args, show help instead of launching GUI.
        if len(sys.argv) == 1:
            sys.argv.append("--help")
        main_cli()
    else:
        # Normal/GUI exe: args → CLI, no args → GUI
        if len(sys.argv) > 1:
            main_cli()
        else:
            main_gui()