import sys
from decklister.deck_image_generator import DeckImageGenerator
from decklister.config import Config

def main():
    # Example: parse args, load config, run generator
    deck_file = sys.argv[1] if len(sys.argv) > 1 else None
    l_b_height=int(391/2.1)
    l_b_width=int(547/2.1)
    config = Config(
        background="TNT-background.png",
        foreground="deck vid border.png",
        forbidden_areas=[
            # [0, 680, 200, 880],
            [1560, 760, 1870, 980],
            [0, 980, 1920, 1080],
        ],
        leader_area=[70, 90, l_b_width + 70, l_b_height + 90],
        base_area=[70, l_b_height + 90, l_b_width + 70, 2 * l_b_height + 90],
        deck_area=[l_b_width + 120, 90, 1870, 750],
        sb_area=[l_b_width + 120, 580, 1550, 980],
        count_background="count_background.png"
    )
    generator = DeckImageGenerator(config=config, blur_count_area=False)
    generator.run(deck_file)

if __name__ == "__main__":
    main()