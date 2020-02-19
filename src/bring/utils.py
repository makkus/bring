# -*- coding: utf-8 -*-
import os
from pathlib import Path
from typing import Union

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
