"""
Build script to generate a static GitHub Pages export of SpendWise.
Renders the public SaaS showcase landing page and assets into `_site/`.
"""

import os
import shutil
import re
from pathlib import Path

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'spendwise.settings')
import django
django.setup()

from django.template.loader import render_to_string

BASE_DIR = Path(__file__).resolve().parent
DIST_DIR = BASE_DIR / '_site'

def build():
    # Clean previous build
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)

    # 1. Copy static assets (css, js, images)
    static_src = BASE_DIR / 'static'
    static_dest = DIST_DIR / 'static'
    if static_src.exists():
        shutil.copytree(static_src, static_dest)

    # 2. Render landing page
    context = {
        'is_landing': True,
        'CURRENT_YEAR': 2026,
        'total_tx_count': 3500,
        'total_categories': 16,
        'total_budgets': 4,
    }
    rendered_html = render_to_string('landing.html', context)

    # Make static asset paths relative for GitHub Pages (e.g. ./static/css/main.css)
    rendered_html = re.sub(r'href="/static/', 'href="./static/', rendered_html)
    rendered_html = re.sub(r'src="/static/', 'src="./static/', rendered_html)
    
    # Update interactive buttons for static GitHub Pages host
    rendered_html = rendered_html.replace('href="/demo-login/"', 'href="#preview"')
    rendered_html = rendered_html.replace('href="/login/"', 'href="#preview"')
    rendered_html = rendered_html.replace('href="/register/"', 'href="https://github.com/arunsarunkumars754-star/Spendwise-track-smarter#readme"')
    rendered_html = rendered_html.replace('href="/api/docs/"', 'href="https://github.com/arunsarunkumars754-star/Spendwise-track-smarter#api-documentation"')

    # Write index.html
    index_file = DIST_DIR / 'index.html'
    index_file.write_text(rendered_html, encoding='utf-8')

    # 3. Create .nojekyll to prevent GitHub Pages from ignoring folders or underscores
    (DIST_DIR / '.nojekyll').touch()

    print(f"Successfully generated static GitHub Pages build in {DIST_DIR}")
    print(f"index.html size: {index_file.stat().st_size} bytes")

if __name__ == '__main__':
    build()
