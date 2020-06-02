# -*- coding: utf-8 -*-
import os
import typing
from collections import Sequence
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple, Union

from bring.defaults import (
    BRING_ALLOWED_MARKER_NAME,
    BRING_METADATA_FOLDER_NAME,
    BRING_TASKS_BASE_TOPIC,
)
from frtls.tasks import TaskDesc


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


def replace_var_aliases(
    vars: Mapping[str, Any], metadata: Mapping[str, Any]
) -> Mapping[str, Any]:

    aliases = metadata.get("aliases", {})
    version_vars = metadata["pkg_vars"]["version_vars"]
    mogrify_vars = metadata["pkg_vars"]["mogrify_vars"]

    relevant_vars = {}

    for k, v in vars.items():
        if k in version_vars.keys():
            relevant_vars[k] = v
        elif k in mogrify_vars.keys():
            relevant_vars[k] = v

    vars_final: Dict[str, Any] = {}
    for k, v in relevant_vars.items():
        if not isinstance(v, str):
            vars_final[k] = v
        else:
            vars_final[k] = aliases.get(k, {}).get(v, v)

    return vars_final


def find_pkg_aliases(
    _pkg_metadata: Mapping[str, Any], **orig_vars: Any
) -> Mapping[str, Optional[str]]:

    aliases = _pkg_metadata.get("aliases", {})
    version_vars = _pkg_metadata["pkg_vars"]["version_vars"]
    mogrify_vars = _pkg_metadata["pkg_vars"]["mogrify_vars"]

    alias_map = {}

    for k, v in orig_vars.items():
        if k in version_vars.keys():
            alias_map[k] = v
        elif k in mogrify_vars.keys():
            alias_map[k] = v

    vars_final: Dict[str, Any] = {}
    for k, v in alias_map.items():
        if not isinstance(v, str):
            vars_final[k] = None
        else:
            vars_final[k] = aliases.get(k, {}).get(v, v)

    return vars_final


def find_versions(
    vars: Mapping[str, str], metadata: Mapping[str, Any], var_aliases_replaced=False
) -> typing.Sequence[Tuple[Mapping[str, Any], int]]:

    versions: Sequence[Mapping] = metadata["versions"]

    if not var_aliases_replaced:
        vars = replace_var_aliases(vars=vars, metadata=metadata)

    # TODO: parse args

    if not vars:
        return [(x, 0) for x in versions]

    matches = []
    for version in versions:

        match = True
        matched_keys = 0
        for k, v in version.items():
            if k == "_meta" or k == "_mogrify":
                continue

            comp_v = vars.get(k, None)
            if comp_v is None:
                continue
            elif not isinstance(comp_v, str) and isinstance(comp_v, Sequence):
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

            matched_keys = matched_keys + 1

        if match:
            matches.append((version, matched_keys))

    return matches


def find_version(
    vars: Mapping[str, str], metadata: Mapping[str, Any], var_aliases_replaced=False
) -> Optional[Mapping[str, Any]]:
    """Return details about one version item of a package, using the provided vars to find one (or the first) version that matches most/all of the provided vars.

        Args:
            - *vars*: User provided vars
            - *metadata*: the package metadata
        """

    matches = find_versions(
        vars=vars, metadata=metadata, var_aliases_replaced=var_aliases_replaced
    )

    if not matches:
        return None

    if len(matches) == 1:
        return matches[0][0]

    # find the first 'exactest" match
    max_match = matches[0]
    for m in matches[1:]:
        if m[1] > max_match[1]:
            max_match = m

    return max_match[0]


class BringTaskDesc(TaskDesc):
    def __init__(self, **kwargs: Any) -> None:

        subtopic = kwargs.pop("subtopic", None)
        if subtopic:
            topic = f"{BRING_TASKS_BASE_TOPIC}.{subtopic}"
        else:
            topic = BRING_TASKS_BASE_TOPIC
        kwargs["topic"] = topic
        super().__init__(**kwargs)
