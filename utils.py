from typing import Optional, Set
import re
import os

import pdf2image
from PIL import Image

_TAG_RE = re.compile(r'<[^>]+>')


def get_image(filename : str) -> Optional[Image.Image]:
    """
    Convenience function to get an `Image` object for a file name.
    Parameters
    ----------
    filename : str
        The filename of the image
    Returns
    -------
    image : Image
        The image object or None if it couldn't be loaded.
    """
    if filename.endswith('.pdf'):
        try:
            images = pdf2image.convert_from_path(filename)
        except Exception:  # FIXME: more specific
            return None
        if len(images) != 1:  # not a single page, maybe a paper?
            return None
        image = images[0]
    else:
        try:
            image = Image.open(filename)
        except Exception:  # FIXME: more specific
            return None
    return image


def remove_tags(html_text : str) -> str:
    """Remove tags from HTML text."""
    return _TAG_RE.sub('', html_text)

def normalize_paths(filenames : Set[str], reference_name: str) -> Set[str]:
    """Normalize relative file names referenced in a script.
    """
    reference_dir = os.path.dirname(reference_name)
    return {os.path.normpath(os.path.join(reference_dir, fname))
            for fname in filenames}
