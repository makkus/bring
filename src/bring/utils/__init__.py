# -*- coding: utf-8 -*-
import os
from collections import Sequence
from pathlib import Path
from typing import Any, Iterable, Mapping, Union

from bring.defaults import BRING_ALLOWED_MARKER_NAME, BRING_METADATA_FOLDER_NAME


def is_valid_bring_target(target: Union[str, Path]):

    if isinstance(target, str):
        _target = Path(os.path.realpath(os.path.expanduser(target)))
    else:
        _target = target.resolve()

    if not _target.exists():
        return True

    if not _target.is_dir():
        return False

    if not any(_target.iterdir()):
        return True

    bring_created_marker = _target / f".{BRING_ALLOWED_MARKER_NAME}"
    if bring_created_marker.exists():
        return True

    metadata_folder = _target / BRING_METADATA_FOLDER_NAME
    if not metadata_folder.exists():
        return False

    bring_created_marker = metadata_folder / BRING_ALLOWED_MARKER_NAME
    if bring_created_marker.exists():
        return True

    return False


def set_folder_bring_allowed(path: Union[str, Path]):

    if isinstance(path, str):
        _path = Path(os.path.realpath(os.path.expanduser(path)))
    else:
        _path = path.resolve()

    metadata_folder = _path / BRING_METADATA_FOLDER_NAME
    metadata_folder.mkdir(parents=True, exist_ok=True)

    marker_file = metadata_folder / BRING_ALLOWED_MARKER_NAME
    marker_file.touch()


def find_versions(
    vars: Mapping[str, str], metadata: Mapping[str, Any]
) -> Iterable[Mapping[str, Any]]:
    aliases = metadata.get("aliases", {})
    # pkg_args = metadata.get("pkg_args", {})
    versions = metadata["versions"]

    version_vars = metadata["pkg_vars"]["version_vars"]

    relevant_vars = {}

    for k, v in vars.items():
        if k in version_vars.keys():
            relevant_vars[k] = v

    # TODO: parse args

    vars_final = {}
    for k, v in relevant_vars.items():
        vars_final[k] = aliases.get(k, {}).get(v, v)

    if not vars_final:
        return versions

    matches = []
    for version in versions:

        match = True
        for k, v in version.items():
            if k == "_meta" or k == "_mogrify":
                continue

            comp_v = vars_final.get(k, None)
            if not isinstance(comp_v, str) and isinstance(comp_v, Sequence):
                temp_match = False
                for c in comp_v:
                    if c == v:
                        temp_match = True
                        break
                if not temp_match:
                    match = False
                    break
            else:

                if comp_v != v:
                    match = False
                    break

        if match:
            matches.append(version)

    return matches


def find_version(
    vars: Mapping[str, str], metadata: Mapping[str, Any]
) -> Mapping[str, Any]:
    """Return details about one version item of a package, using the provided vars to find one (or the first) version that matches most/all of the provided vars.

        Args:
            - *vars*: User provided vars
            - *metadata*: the package metadata
        """

    matches = find_versions(vars=vars, metadata=metadata)

    if not matches:
        return None

    if len(matches) == 1:
        return matches[0]

    # find the first 'exactest" match
    max_match = matches[0]
    for m in matches[1:]:
        if len(m) > len(max_match):
            max_match = m

    return max_match
