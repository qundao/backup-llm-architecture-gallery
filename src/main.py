import logging
import random
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import curl_cffi
import feedparser
import pandas as pd
from lxml import html

RSS_URL = "https://sebastianraschka.com/llm-architecture-gallery/rss.xml"
BLOG_URL = "https://sebastianraschka.com/llm-architecture-gallery/"
VERSION_FILE = "version.txt"
IMAGE_DIR = "images"
DATA_TSV_FILE = "llm-list.tsv"


def _download_image(url, save_dir, save_name=None, overwrite=False):
    if not save_name:
        save_name = url.split("/")[-1]

    save_path = Path(save_dir, save_name)
    if not overwrite and save_path.exists():
        logging.info(f"Ignore existed image {save_name}")
        return

    if not url.startswith("http"):
        url = urljoin(BLOG_URL, url)
    logging.info(f"Request = {url} -> {save_name}")

    r = curl_cffi.get(url, stream=True)
    if r.status_code != 200:
        logging.warning(f"Request failed status = {r.status_code}")
        return

    if save_path.exists():
        save_path.unlink()
    save_path.parent.mkdir(parents=True, exist_ok=True)
    with open(save_path, "wb") as f:
        for chunk in r.iter_content():
            f.write(chunk)

    time.sleep(random.random())


def _parse_model(element):
    def to_str(e, pattern):
        return " ".join([v.strip() for v in e.xpath(f"{pattern}//text()")]).strip()

    title = to_str(element, ".//h4")
    summary = to_str(element, ".//p[@class='llm-architecture-overview__fact-summary']")
    links = {a.text_content().strip(): a.get("href") for a in element.xpath(".//div[@class='llm-architecture-overview__title-meta']//a")}
    details = {to_str(e, "./dt"): to_str(e, "./dd") for e in element.xpath(".//dl[@class='llm-architecture-overview__fact-grid']/div")}

    result = {"title": title, "summary": summary} | details | links
    return result


def parse_blog(version, overwrite=False):
    response = curl_cffi.get(BLOG_URL)
    if response.status_code != 200:
        logging.info(f"Error = {response.status_code}")
        return False

    text = response.text
    tree = html.fromstring(text)

    model_list = tree.xpath('//article[@class="llm-architecture-overview__card"]')
    # model_data = [{k: v for k, v in element.attrib.items() if k.startswith("data-")} for element in model_list]
    model_data = [_parse_model(element) for element in model_list]
    logging.info(f"Models = {len(model_list)}")

    df = pd.DataFrame(model_data)
    df = df.sort_values(["Date", "title"])
    df.to_csv(DATA_TSV_FILE, index=False, sep="\t")
    logging.info(f"Save {df.shape} to {DATA_TSV_FILE}")

    cover_images = tree.xpath('//*[@id="main-content"]//article//section[1]/figure/button/img/@src')
    model_images = tree.xpath('//article[@class="llm-architecture-overview__card"]//img/@src')
    if cover_images:
        cover_url = cover_images[0]
        cover_name = cover_url.split("/")[-1]
        if version:
            filename, extension = cover_name.split(".")
            cover_name = f"{filename}-{version}.{extension}"
        _download_image(cover_url, ".", cover_name, overwrite=overwrite)
    for image_url in model_images:
        _download_image(image_url, IMAGE_DIR, overwrite=overwrite)
    return True


def parse_rss():
    logging.info("Read rss")
    d = feedparser.parse(RSS_URL)
    entries = d["entries"]
    logging.info(f"Rss feeds = {len(entries)}")
    if len(entries) == 0:
        logging.warning("No entries")
        return

    entry = entries[0]  # latest
    # title = entry["title"]
    # link = entry["link"]
    # summary = entry['summary']
    published = entry["published"]
    pub_date = datetime.strptime(published, "%a, %d %b %Y %H:%M:%S %z")
    pub_version = pub_date.strftime("v%Y.%m.%d")
    with open(VERSION_FILE) as f:
        version = f.read().strip()

    if version == pub_version:
        logging.info("No new version")
        return
    logging.info(f"New version to update {version} => {pub_version}")

    pub_dt = pub_date.strftime("%Y%m%d")
    if parse_blog(pub_dt):
        with open(VERSION_FILE, "w") as f:
            f.write(pub_version)


if __name__ == "__main__":
    fmt = "%(asctime)s %(levelname)s %(message)s"
    logging.basicConfig(level=logging.INFO, format=fmt)
    parse_rss()
