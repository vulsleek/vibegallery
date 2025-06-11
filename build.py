import os
import shutil
import markdown
import yaml
from pathlib import Path
from datetime import datetime
from PIL import Image
from jinja2 import Environment, FileSystemLoader

# Constants
ROOT = Path(__file__).parent
TEMPLATES_DIR = ROOT / "templates"
DATA_DIR = ROOT / "data"
IMG_DIR = ROOT / "img"
OUT_DIR = ROOT / "out"
THUMB_DIR = OUT_DIR / "thumbs"
POSTS_PREFIX = "/posts"

# Load config
with open(ROOT / "config.yaml") as f:
    config = yaml.safe_load(f)

SITE_NAME = config.get("site_name", "My Site")
SITE_URL = config.get("site_url", "").rstrip("/")  # Empty for local preview
POSTS_SUBDIR = config.get("posts_subdir", "posts")  # can be "" for root

env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))

def render_template(template_name, **context):
    template = env.get_template(template_name)
    return template.render(**context)

def parse_post(md_path):
    with open(md_path, encoding="utf-8") as f:
        content = f.read()

    if content.startswith("---"):
        _, fm, body = content.split("---", 2)
        meta = yaml.safe_load(fm.strip())
    else:
        meta = {}
        body = content

    # Basic metadata
    slug = md_path.stem
    meta["slug"] = slug
    meta["source"] = md_path
    meta["date"] = meta.get("date", datetime.today().date())
    if isinstance(meta["date"], str):
        meta["date"] = datetime.strptime(meta["date"], "%Y-%m-%d").date()

    # Template URL
    post_path = f"{POSTS_SUBDIR}/{slug}.html" if POSTS_SUBDIR else f"{slug}.html"
    meta["url"] = f"/{post_path}"

    # Full URL (for RSS only)
    meta["full_url"] = f"{SITE_URL}/{post_path}" if SITE_URL else meta["url"]

    # Frontmatter tags fallback
    meta["tags"] = meta.get("tags", [])

    # Handle img or imgs
    imgs = meta.get("img", [])
    if isinstance(imgs, str):
        imgs = [imgs]
    meta["images"] = imgs

    # Parse markdown body
    meta["body"] = markdown.markdown(body.strip())

    return meta

def write_file(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def generate_thumbnail(src_img, thumb_path, size=(200, 200)):
    with Image.open(src_img) as im:
        # Crop to square
        min_dim = min(im.size)
        left = (im.width - min_dim) // 2
        top = (im.height - min_dim) // 2
        right = left + min_dim
        bottom = top + min_dim
        cropped = im.crop((left, top, right, bottom))
        cropped.thumbnail(size)
        cropped.save(thumb_path)

def generate_thumbnails(posts):
    for post in posts:
        for img in post["images"]:
            img_path = IMG_DIR / img
            thumb_path = THUMB_DIR / img
            if not thumb_path.exists():
                thumb_path.parent.mkdir(parents=True, exist_ok=True)
                generate_thumbnail(img_path, thumb_path)
                print(f"Generated thumbnail for {img}")

def build_post_pages(posts):
    tmpl_path = TEMPLATES_DIR / "post.html"
    for post in posts:
        output_path = OUT_DIR / post["url"].lstrip("/")
        if output_path.exists():
            out_mtime = output_path.stat().st_mtime
            if post["source"].stat().st_mtime < out_mtime and tmpl_path.stat().st_mtime < out_mtime:
                continue
        html = render_template("post.html", site_name=SITE_NAME, post=post)
        write_file(output_path, html)

def build_index_page(posts):
    posts_sorted = sorted(posts, key=lambda p: p["date"], reverse=True)
    html = render_template("index.html", site_name=SITE_NAME, posts=posts_sorted)
    write_file(OUT_DIR / "index.html", html)

def build_tag_pages(posts):
    tags = {}
    for post in posts:
        for tag in post["tags"]:
            tags.setdefault(tag, []).append(post)

    for tag, tag_posts in tags.items():
        tag_posts = sorted(tag_posts, key=lambda p: p["date"], reverse=True)
        html = render_template("tag.html", site_name=SITE_NAME, tag=tag, posts=tag_posts)
        write_file(OUT_DIR / f"tag-{tag}.html", html)

def build_rss(posts):
    posts_sorted = sorted(posts, key=lambda p: p["date"], reverse=True)[:10]
    rss = render_template("rss.xml", site_name=SITE_NAME, site_url=SITE_URL, posts=posts_sorted)
    write_file(OUT_DIR / "rss.xml", rss)

def copy_static():
    static_dirs = ["img"]
    for name in static_dirs:
        src = ROOT / name
        dest = OUT_DIR / name
        if src.exists():
            shutil.copytree(src, dest, dirs_exist_ok=True)
            print(f"Copied static /{name}")

    # Copy /static contents directly into OUT_DIR
    static_root = ROOT / "static"
    if static_root.exists():
        for item in static_root.rglob("*"):
            if item.is_file():
                rel_path = item.relative_to(static_root)
                dest_path = OUT_DIR / rel_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest_path)
        print("Copied /static contents into root of /out")

    # Also handle styles.css if kept in /templates
    css_src = TEMPLATES_DIR / "styles.css"
    if css_src.exists():
        shutil.copy(css_src, OUT_DIR / "styles.css")
        print("Copied styles.css")


def main():
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir()
    THUMB_DIR.mkdir(parents=True, exist_ok=True)

    copy_static()

    posts = []
    for md_file in DATA_DIR.glob("*.md"):
        post = parse_post(md_file)
        posts.append(post)

    generate_thumbnails(posts)
    build_post_pages(posts)
    build_index_page(posts)
    build_tag_pages(posts)
    build_rss(posts)
    print("Site build complete.")

if __name__ == "__main__":
    main()