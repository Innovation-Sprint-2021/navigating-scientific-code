from subprocess import run


def find_repository_urls(user_input: str) -> dict[str, float]:
    """Given user input, resolve to proper git URL.

    For expected URL https://github.com/krassowski/multi-omics-state-of-the-field,
    following user inputes should be accepted and harmonized:
     - `https://github.com/krassowski/multi-omics-state-of-the-field`
     - `github.com/krassowski/multi-omics-state-of-the-field`
     - `krassowski/multi-omics-state-of-the-field`
         - should check if github.com and gitlab.com; if both exists should return both
     - `git@github.com:krassowski/multi-omics-state-of-the-field.git`
     - `https://doi.org/10.3389/fgene.2020.610798`
        - should use JSON API and
         then Entrez (or something else) to scan abstract and then the full
         text for git URLs (there are multiple matches; it should give them
         confidence proportional to number of matches for now; in future could
         use some more intelligent ciriteria).

    Returns:
        a mapping between the resolved/guessed URL and the confidence score
        in the match (0, 1]; the mapping should be sorted by confidence from
        best match to the worst match

    Raises:
       `ValueError` if the repository cannot be found,
       with an informative error message to be shown to the user.
    """
    # TODO (setup pytest → write unit → implement)
    return {
        user_input: 1
    }


def fetch_repository(address: str, temp_dir: str):
    """Clone the repository into specified directory"""
    return run(
        ['git', 'clone', '--depth=1', address, temp_dir],
        check=True,
        # TODO: uncomment (for now good ok debugging)
        # capture_output=True
    )
