import os
import tempfile

import retrieval
import extraction

# Prepare temporary directories to store the repository and image files from
# the elife article
repo_dir = tempfile.mkdtemp()
image_dir = tempfile.mkdtemp()

ARTICLE_ID = '67509'  # https://elifesciences.org/articles/67509

print('Fetching article')
article = retrieval.fetch_article('elife', ARTICLE_ID)
user, repo = extraction.find_github_repo(article)
repo_url = retrieval.repo_url(user, repo)
print(f'Cloning {repo_url}')
retrieval.fetch_repository(repo_url, repo_dir)

manifest = extraction.create_manifest(repo_dir)

print('Adding information from the readme files to the manifest')
extraction.augment_from_readmes(manifest, repo_dir)

print('Adding information from the r files to the manifest')
extraction.augment_from_r(manifest, repo_dir)

print('Adding information from the article to the manifest')
extraction.augment_from_elife(article['body'], manifest, image_dir, repo_dir,
                              id=ARTICLE_ID)

print('Final manifest:')
# (For display purposes, remove empty references)
for metadata in manifest.values():
    if not len(metadata['references']):
        del metadata['references']
import pprint
pprint.pprint(manifest)
