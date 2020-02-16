# -*- coding: utf-8 -*-
import os
import shutil
from typing import Dict

from frtls.defaults import DEFAULT_EXCLUDE_DIRS
from frtls.files import ensure_folder

from bring.transform import TransformException, Transformer


class MergeTransformer(Transformer):

    _plugin_name: str = "merge"

    def __init__(self, **config):

        super().__init__(**config)

    def get_config_keys(self) -> Dict:

        return {"merge_strategy": "default", "sources": None, "delete_sources": False}

    def _transform(self, path: str, transform_config: Dict = None) -> str:

        strategy = transform_config["merge_strategy"]
        if isinstance(strategy, str):
            strategy = {"type": strategy}

        sources = transform_config["sources"]
        if sources is None:
            raise Exception("Can't merge directories, no sources provided.")

        if isinstance(sources, str):
            sources = [sources]

        delete_sources = transform_config["delete_sources"]

        for source in sources:

            self.process_folder(source=source, target=path, strategy=strategy)
            if delete_sources:
                shutil.rmtree(source)

        return path

    def process_folder(self, source: str, target: str, strategy: Dict):

        exclude_dirs = strategy.get("exclude_dirs", DEFAULT_EXCLUDE_DIRS)

        strategy_type = strategy["type"]
        if not hasattr(self, f"merge_{strategy_type}"):
            raise Exception(f"No '{strategy_type}' merge strategy implemented.")

        func = getattr(self, f"merge_{strategy_type}")

        for root, dirnames, filenames in os.walk(source, topdown=True):

            if exclude_dirs:
                dirnames[:] = [d for d in dirnames if d not in exclude_dirs]

            for filename in filenames:

                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, source)

                func(source, target, rel_path, strategy)

    def merge_default(
        self, source_base: str, target_base: str, rel_path: str, strategy_config: Dict
    ):

        target = os.path.join(target_base, rel_path)
        if os.path.exists(target):
            raise TransformException(
                msg=f"Can't merge file '{rel_path}'.",
                reason=f"File already exists in target: {target_base}",
            )

        source = os.path.join(source_base, rel_path)

        ensure_folder(os.path.dirname(target))
        shutil.move(source, target)
