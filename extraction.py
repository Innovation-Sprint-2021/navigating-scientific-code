from typing import List
import mimetypes
import os
import re

import requests
from skimage.metrics import structural_similarity as ssim
import numpy as np
import lxml.html
import markdown

import utils


def find_github_repo(article: dict) -> (str, str):
    """
    Recusively go through the structured article representation to find
    a reference to a github URL.

    Parameters
    ----------
    article : dict
        Structured article representation

    Returns
    -------
    user, repo
        The user (or organization) name and the repository name.
    """
    # TODO: assumes only a single repository in the text
    for block in article:
        if block['type'] == 'paragraph':
            text = utils.remove_tags(block['text'])
            # TODO: Only matches main repo, not branches, etc.
            match = re.search(r'https://github.com/([a-zA-Z0-9-]+)/([a-zA-Z0-9_\-]+)\b', text)
            if match:
                return match.group(1), match.group(2)
        elif block['type'] == 'section':
            result = find_github_repo(block['content'])
            if result:
                return result
        else:  # figure, etc.
            continue


def create_manifest(repo_dir: str) -> dict:
    """
    Create a basic manifest mapping all filenames in a directory to additional
    data related to that file.

    Parameters
    ----------
    repo_dir : str
        Where to start crawling.

    Returns
    -------
    manifest : dict
    """
    manifest = {}
    for root, dirs, files in os.walk(repo_dir):
        # quick&dirty way to only retain the path in the repo
        dirname = root[len(repo_dir) + 1:]
        for fname in files:
            if '.git' in dirname:
                continue
            mime_type, _ = mimetypes.guess_type(fname, strict=False)
            manifest[os.path.join(dirname, fname)] = {'type': mime_type,
                                                      'references': []
                                                      }
    return manifest


def augment_from_elife(article: dict, manifest: dict,
                       tmp_dir: str, repo_dir: str,
                       id: str, path=None):
    """
    Augment the manifest with information from an elife article

    Parameters
    ----------
    article : dict
        Structured representation of the article
    manifest : dict
        A manifest dictionary – note that this dictionary will be directly
        updated.
    tmp_dir : str
        Temporary directory to store figure files
    repo_dir : str
        Name of the directory where the repository files are stored
    id : str
        An id describing the article.
    path
        Argument to track the section structure in recursive calls.
    """
    if path is None:
        path = []
    for block in article:
        if block['type'] == 'paragraph':
            text = utils.remove_tags(block['text'])
            for filename in manifest:
                basename = os.path.basename(filename)
                if '.' not in basename:  # skip too generic filenames like "description"
                    continue
                if basename in text:
                    manifest[filename]['references'].append({'origin': id,
                                                             'context': text,
                                                             'section': ' → '.join(path)})
        elif block['type'] == 'figure':
            for image_block in block['assets']:
                if not 'image' in image_block:
                    continue
                source_file = os.path.join(tmp_dir,
                                           image_block['image']['source']['filename'])
                if not os.path.exists(source_file):
                    # Download the source image
                    response = requests.get(image_block['image']['source']['uri'], allow_redirects=True)
                    with open(source_file, 'wb') as f:
                        f.write(response.content)
                source_image = utils.get_image(source_file)
                if source_image is None:
                    continue
                print(f'Comparing {source_file} to images in the repo')
                # Compare to all known images
                for repo_file, metadata in manifest.items():
                    if not 'notebooks/figures' in repo_file:
                        continue
                    if (metadata['type'] is None
                            or not (metadata['type'] == 'application/pdf' or metadata['type'].startswith('image/'))):
                        continue
                    repo_image = utils.get_image(os.path.join(repo_dir, repo_file))
                    if repo_image is None:
                        continue
                    if repo_image.size != source_image.size:
                        repo_aspect = repo_image.size[0] / repo_image.size[1]
                        source_aspect = source_image.size[0] / source_image.size[1]
                        if abs(repo_aspect - source_aspect) > 0.01:
                            continue
                        if repo_image.size[0] < source_image.size[0]:  # scale to repo_image size
                            scaled_repo_image = repo_image
                            scaled_source_image = source_image.resize(repo_image.size)
                        else:  # scale to source image size
                            scaled_repo_image = repo_image.resize(source_image.size)
                            scaled_source_image = source_image
                    else:
                        # No scaling necessary
                        scaled_repo_image = repo_image
                        scaled_source_image = source_image

                    # Compare with structural similary
                    similarity = ssim(np.asarray(scaled_repo_image),
                                      np.asarray(scaled_source_image),
                                      multichannel=True)
                    if similarity > 0.9:
                        print(f"Found a match {repo_file} == {image_block['label']}!", repo_file)
                        metadata['references'].append({'origin': f'elife/{id}',
                                                       'context': image_block['title'],
                                                       'label': image_block['label']})

        elif block['type'] == 'section':
            augment_from_elife(block['content'], manifest, tmp_dir, repo_dir, id=id,
                               path=path + [block['title']])
        else:
            continue

def readme_files(manifest: dict) -> List[str]:
    """Get the names of all readme files in the manifest
    Parameters
    ----------
    manifest : dict
        The manifest

    Returns
    -------
    readme_files : List[str]
        list of readme file names
    """
    readme_names = ['readme', 'readme.md', 'readme.txt', 'readme.html']
    return [fname for fname in manifest
            if os.path.basename(fname).lower() in readme_names]

# A few helper functions to find filenames in html files (potentially converted
# from markdown)
def _find_filename_in_tree(tree, filename):
    for el in tree.iter():
        if el.text is not None and filename in el.text:
            return el
        if el.tail is not None and filename in el.tail:
            return el


def _get_context_paragraph(tree):
    if tree.tag in ('p', 'li') or tree.getparent() is None:
        return tree.text_content()
    else:
        return _get_context_paragraph(tree.getparent())


def _get_headers(tree, headers=None):
    if headers is None:
        headers = []
    if tree.tag in ('h1', 'h2', 'h3', 'h4'):  # FIXME...
        headers.append(tree.text_content())
    if tree.getprevious() is not None:
        return _get_headers(tree.getprevious(), headers=headers)
    elif tree.getparent() is not None:
        return _get_headers(tree.getparent(), headers=headers)
    else:
        return headers

def _find_filename_in_html(text, filename):
    parsed = lxml.html.fromstring(text)
    found = _find_filename_in_tree(parsed, filename)
    assert found is not None
    # Get context paragraph and possible headers
    paragraph = _get_context_paragraph(found)
    headers = ' → '.join(reversed(_get_headers(found)))
    return paragraph, headers


def augment_from_readmes(manifest: dict, repo_dir: str):
    """
    Augment the manifest with information from the readme files.

    Parameters
    ----------
    manifest : dict
        The manifest, updated when running this function.
    repo_dir : str
        Name of the directory where the repository files are stored
    """
    readmes = readme_files(manifest)
    for readme in readmes:
        readme_text = open(os.path.join(repo_dir, readme)).read()
        for filename, metadata in manifest.items():
            if '.' not in filename or filename in readmes:
                continue
            if filename in readme_text:
                if readme.endswith('.md'):
                    html_text = markdown.markdown(readme_text)
                    par, headers = _find_filename_in_html(html_text, filename)
                    metadata['references'].append({'origin': readme,
                                                   'context': par,
                                                   'section': headers})
                else:
                    # TODO: Not sure the following is useful (trying to extract
                    #       some relevant context from text files)
                    description = re.search(f"""["'`]?{filename}["'`]??(:| is| contains)?(.*\n)""", readme_text)
                    if description:
                        metadata['references'].append({'origin': readme,
                                                       'context': description.group(0)})
                    else:
                        description = re.search(f"""?([\n^]).*{filename}.*?([\n$])""", readme_text)
                        if description:
                            metadata['references'].append({'origin': readme,
                                                           'context': description.group(0)})
                        else:
                            metadata['references'].append({'origin': readme})

def _input_output_r(content):
    # FIXME: more robust parsing
    inputs = re.findall("""read_[ct]sv\(['"]([\.\/\-_0-9a-zA-Z]+)['"][^)]*\)""", content)
    inputs.extend(re.findall("""load\(['"]([\.\/\-_0-9a-zA-Z]+)['"]\)""", content))
    outputs = re.findall("""write_[ct]sv\([^,]+,\s*['"]([\.\/\-_0-9a-zA-Z]+)['"][^)]*\)""", content)
    outputs.extend(re.findall("""pdf\(['"]([\.\/\-_0-9a-zA-Z]+)['"][^)]*\)""", content))
    outputs.extend(re.findall("""save\(.*, file=['"]([\.\/\-_0-9a-zA-Z]+)['"][^)]*\)""", content))
    dependencies = re.findall("""source\(['"]([\.\/\-_0-9a-zA-Z]+)['"]\)""", content)
    return set(inputs), set(outputs), set(dependencies)


def augment_from_r(manifest, repo_dir):
    for filename, metadata in manifest.items():
        if not filename.endswith('.r'):
            continue

        with open(os.path.join(repo_dir, filename), 'r') as f:
            lines = f.readlines()
            cleaned_lines = [l for l in lines if not l.strip().startswith('#')]
            content = '\n'.join(cleaned_lines)
            inputs, outputs, dependencies = _input_output_r(content)
            metadata['inputs'] = utils.normalize_paths(inputs, filename)
            metadata['outputs'] = utils.normalize_paths(outputs, filename)
            metadata['dependencies'] = utils.normalize_paths(dependencies, filename)
