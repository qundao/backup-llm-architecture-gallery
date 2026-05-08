import argparse
import logging
import math
from pathlib import Path

from PIL import Image

BG_COLOR = (255, 255, 255)  # default white background
# MAX_IMAGE_SIZE = (1024, 1024)  # max images size [optional]
SAVE_FILE = "architecture-gallery-hero-all.jpg"
IMAGE_DIR = "images"


def get_image_files(image_dir):
    image_extensions = ("*.png", "*.jpg", "*.jpeg", "*.webp")
    files = []
    for ext in image_extensions:
        files.extend(Path(image_dir).glob(ext))
    return sorted([f for f in files if not f.name.startswith(".")])


def scale_image(image, max_height):
    w, h = image.size
    new_w = int(w * (max_height / h))
    img = image.resize((new_w, max_height), Image.LANCZOS)
    return img


def load_images(image_files, max_height, limit=0):
    images = []
    for file in image_files:
        try:
            img = Image.open(file)
            if max_height:
                img = scale_image(img, max_height)
            if img.mode in ("LA", "P"):
                img = img.convert("RGBA")
            images.append(img)
        except Exception as e:
            logging.warning(f"Read image failed{file}: {e}")

    if limit > 0:
        images = images[:limit]

    return images


def compute_grid_size(images, images_per_row, margin):
    if not images:
        return 0, 0, 0, 0

    max_w = max(img.width for img in images)
    max_h = max(img.height for img in images)
    cell_w = max_w
    cell_h = max_h

    num_images = len(images)
    num_cols = images_per_row
    num_rows = math.ceil(num_images / num_cols)
    grid_w = num_cols * cell_w + (num_cols + 1) * margin
    grid_h = num_rows * cell_h + (num_rows + 1) * margin

    return grid_w, grid_h, cell_w, cell_h


def paste_images(grid_image, images, images_per_row, cell_w, cell_h, margin):
    max_w = cell_w
    max_h = cell_h

    for idx, img in enumerate(images):
        row = idx // images_per_row
        col = idx % images_per_row

        base_x = margin + col * (cell_w + margin)
        base_y = margin + row * (cell_h + margin)

        offset_x = (max_w - img.width) // 2
        offset_y = (max_h - img.height) // 2

        paste_x = base_x + offset_x
        paste_y = base_y + offset_y

        if img.mode == "RGBA":
            grid_image.paste(img, (paste_x, paste_y), img)
        else:
            grid_image.paste(img, (paste_x, paste_y))


def merge_all_images(image_dir, save_file, *, images_per_row, image_margin, image_limit, height_size):
    image_files = get_image_files(image_dir)
    logging.info(f"Find {len(image_files)} images in dir = {image_dir}")

    images = load_images(image_files, max_height=height_size, limit=image_limit)
    logging.info(f"Read {len(images)} images")

    if not images:
        logging.info("No image files, exit")
        return

    if images_per_row <= 0:
        images_per_row = int(math.sqrt(len(images)))
        logging.info(f"Images per row = {images_per_row}")

    # Image.MAX_IMAGE_PIXELS = None
    grid_w, grid_h, cell_w, cell_h = compute_grid_size(images, images_per_row, image_margin)
    logging.info(f"Full images size =  {grid_w}x{grid_h}, single cell size: {cell_w}x{cell_h}")

    grid_image = Image.new("RGB", (grid_w, grid_h), BG_COLOR)
    paste_images(grid_image, images, images_per_row, cell_w, cell_h, image_margin)

    save_path = Path(save_file)
    if not save_path.parent.exists():
        save_path.parent.mkdir(parents=True)

    if height_size > 0:
        save_path = Path(save_path.parent, f"{save_path.stem}-{height_size}{save_path.suffix}")
    logging.info(f"Save to {save_path}")
    grid_image.save(save_path)
    logging.info("Save Done")


if __name__ == "__main__":
    fmt = "%(asctime)s %(levelname)s %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt)

    parser = argparse.ArgumentParser(description="Stitches all images in a directory into a grid layout.")
    parser.add_argument("--data", type=str, default=IMAGE_DIR, help="Directory containing the images.")
    parser.add_argument("--save", type=str, default=SAVE_FILE, help="Output filename.")
    parser.add_argument("--row", type=int, default=0, help="Number of images per row.")
    parser.add_argument("--margin", type=int, default=20, help="Spacing between images.")
    parser.add_argument("--limit", type=int, default=0, help="Limit the number of images to process (0 for no limit).")
    parser.add_argument("--height", type=int, default=0, help="")

    args = parser.parse_args()
    merge_all_images(
        args.data,
        args.save,
        images_per_row=args.row,
        image_margin=args.margin,
        image_limit=args.limit,
        height_size=args.height,
    )
