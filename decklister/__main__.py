import sys
from decklister.deck_image_generator import DeckImageGenerator
from decklister.config import Config

def main():
    # Example: parse args, load config, run generator
    deck_file = sys.argv[1] if len(sys.argv) > 1 else None
    l_b_height=int(391/1.7)
    l_b_width=int(547/1.7)
    config = Config(
        background="TNT-background.png",
        foreground="deck vid border.png",
        forbidden_areas=[
            [0, 680, 200, 880],
            [1720, 880, 1920, 1080],
            [0, 980, 1920, 1080],
        ],
        leader_area=[60, 80, l_b_width + 60, l_b_height + 80],
        base_area=[60, l_b_height + 90, l_b_width + 60, 2 * l_b_height + 90],
    )
    generator = DeckImageGenerator(config=config, blur_count_area=False)
    generator.run(deck_file)

if __name__ == "__main__":
    main()