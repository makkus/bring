# -*- coding: utf-8 -*-
import gzip
import os
import shutil
from typing import Any, Mapping

from bring.mogrify import SimpleMogrifier
from frtls.exceptions import FrklException
from frtls.files import ensure_folder


class ExtractMogrifier(SimpleMogrifier):
    """Extract an archive.

    This mogrifier is used internally, and, for now, can't be used in user-created mogrifier lists.

    Supported archive formats:
      - zip
      - tar
      - gztar
      - bztar
      - xztar
    """

    _plugin_name = "extract"

    _requires = {"file_path": "string", "remove_root": "boolean?"}
    _provides = {"folder_path": "string"}

    # def __init__(self, name: str, meta: TingMeta):
    #
    #     super().__init__(name=name, meta=meta)

    def get_msg(self) -> str:

        vals = self.user_input

        result = "extracting archive"

        if vals.get("file_path", None):
            result = result + f" '{vals['file_path']}'"

        if vals.get("remove_root", None):
            result = result + " (disregarding root folder, only using contents of it)"
        return result

    async def mogrify(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        artefact_path = requirements["file_path"]
        remove_root = requirements.get("remove_root", None)

        base_target = self.create_temp_dir("extract_")
        target_folder = os.path.join(base_target, "extracted")

        extract_folder = os.path.join(base_target, "extract")

        if artefact_path.endswith(".gz") and not artefact_path.endswith(".tar.gz"):
            new_file_name = os.path.basename(artefact_path)[0:-3]
            ensure_folder(extract_folder)
            new_path = os.path.join(extract_folder, new_file_name)
            with gzip.open(artefact_path, "rb") as f_in:
                with open(new_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            shutil.unpack_archive(artefact_path, extract_folder)

        if remove_root is None:
            childs = os.listdir(extract_folder)
            if len(childs) == 1 and os.path.isdir(
                os.path.join(extract_folder, childs[0])
            ):
                remove_root = True
            else:
                remove_root = False

        if remove_root:
            childs = os.listdir(extract_folder)
            if len(childs) == 0:
                raise FrklException(
                    msg="Can't remove archive subfolder.",
                    reason=f"No root file/folder for extracted archive: {artefact_path}",
                )
            elif len(childs) > 1:
                raise FrklException(
                    msg="Can't remove archive subfolder.",
                    reason=f"More than one root files/folders: {', '.join(childs)}",
                )

            root = os.path.join(extract_folder, childs[0])
            if not os.path.isdir(root):
                raise FrklException(
                    msg="Can't remove archive root.",
                    reason=f"Not a folder: {childs[0]}",
                )
            shutil.move(root, target_folder)
            shutil.rmtree(extract_folder)
        else:
            shutil.move(extract_folder, target_folder)

        return {"folder_path": target_folder}
