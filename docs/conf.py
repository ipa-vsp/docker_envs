"""Sphinx configuration for the docker_envs documentation.

The Markdown guides next to the code (README.md, creator/README.md, ...) stay the
single source of truth. At build start they are copied into ``_generated/`` and
their relative links are rewritten: links to another guide become Sphinx
cross-references, links to any other repository file point at GitHub.
"""

import posixpath
import re
import shutil
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent
REPO_ROOT = DOCS_DIR.parent
GENERATED = DOCS_DIR / "_generated"
GITHUB = "https://github.com/ipa-vsp/docker_envs"
BRANCH = "main"

# Repository guide -> page name under _generated/.
GUIDES = {
    "README.md": "overview",
    "docs/ISAAC_WORKFLOW.md": "isaac-workflow",
    "creator/README.md": "creator",
    "gui/README.md": "gui",
    "composer/template/README.md": "composer-template",
    "composer/isaaclab/README.md": "composer-isaaclab",
    "composer/isaacsim/README.md": "composer-isaacsim",
    "composer/isaac/README.md": "composer-isaac",
    "composer/canopen/README.md": "composer-canopen",
    "composer/canopen/patches/README.md": "composer-canopen-patches",
    "composer/rexroth/scripts/README.md": "composer-rexroth-scripts",
}

# -- Project -----------------------------------------------------------------

project = "docker_envs"
author = "ipa-vsp"
copyright = "ipa-vsp"

extensions = [
    "myst_parser",
    "sphinx_design",
    "sphinx_copybutton",
]

source_suffix = {".rst": "restructuredtext", ".md": "markdown"}
root_doc = "index"
exclude_patterns = ["_build", ".venv", "ISAAC_WORKFLOW.md", "Thumbs.db", ".DS_Store"]

myst_enable_extensions = ["colon_fence", "deflist"]
# GitHub-style anchors, so "creator.md#uv-sync-permission-denied" resolves.
myst_heading_anchors = 4


# -- HTML --------------------------------------------------------------------

html_theme = "furo"
html_title = "docker_envs"
html_static_path = []
html_theme_options = {
    "source_repository": f"{GITHUB}/",
    "source_branch": BRANCH,
    "source_directory": "docs/",
}
copybutton_prompt_text = r"^\$ |^PS> "
copybutton_prompt_is_regexp = True

# -- Guide import ------------------------------------------------------------

_LINK = re.compile(r"(\]\()([^)\s]+)(\))")


def _rewrite(target: str, source: str) -> str:
    if re.match(r"^[a-z][a-z0-9+.-]*:", target) or target.startswith("#"):
        return target
    path, _, anchor = target.partition("#")
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source), path))
    if resolved in GUIDES:
        link = f"{GUIDES[resolved]}.md"
        return f"{link}#{anchor}" if anchor else link
    kind = "tree" if (REPO_ROOT / resolved).is_dir() else "blob"
    url = f"{GITHUB}/{kind}/{BRANCH}/{resolved}"
    return f"{url}#{anchor}" if anchor else url


def import_guides(app):
    if GENERATED.exists():
        shutil.rmtree(GENERATED)
    GENERATED.mkdir()
    for source, name in GUIDES.items():
        text = (REPO_ROOT / source).read_text(encoding="utf-8")
        text = _LINK.sub(lambda m: m.group(1) + _rewrite(m.group(2), source) + m.group(3), text)
        note = (
            f"<!-- Generated from {source} by docs/conf.py. Edit the original. -->\n"
            f"\n:::{{note}}\nSource: [`{source}`]({GITHUB}/blob/{BRANCH}/{source})\n:::\n\n"
        )
        # Keep the page title first so it names the page in the navigation.
        title, _, body = text.partition("\n")
        (GENERATED / f"{name}.md").write_text(f"{title}\n{note}{body}", encoding="utf-8")


def setup(app):
    app.connect("builder-inited", import_guides)
