# -*- coding: utf-8 -*-
import copy
import logging
import os
import shutil
import tempfile
from abc import ABCMeta, abstractmethod
from typing import Any, Dict, Iterable, List, Type

from bring.defaults import BRING_WORKSPACE_FOLDER
from frtls.exceptions import FrklException
from frtls.strings import from_camel_case
from frtls.types.typistry import TypistryPluginManager
from pathspec import PathSpec, patterns
from tings.ting import SimpleTing


log = logging.getLogger("bring")


class Transformer(metaclass=ABCMeta):
    def __init__(self, name=None, **config):

        config.pop("type", None)
        self._config = config
        self._merged_config = None

        if name is None:
            name = self.__class__.name
        self._name = name

    @property
    def name(self):
        return self._name

    def find_matches(
        self, path: str, transform_config: Dict, output_absolute_paths=False
    ) -> Iterable:

        include_patterns = transform_config["include"]
        if isinstance(include_patterns, str):
            include_patterns = [include_patterns]

        path_spec = PathSpec.from_lines(patterns.GitWildMatchPattern, include_patterns)

        matches = path_spec.match_tree(path)

        if output_absolute_paths:
            matches = (os.path.join(path, m) for m in matches)

        return matches

    def create_temp_dir(self, prefix=None):

        if prefix is None:
            prefix = from_camel_case(self.__class__.__name__)
        tempdir = tempfile.mkdtemp(prefix=f"{prefix}_", dir=BRING_WORKSPACE_FOLDER)
        return tempdir

    def transform(self, path: str, transform_config: Dict = None) -> str:

        final_config = copy.copy(self.config)
        for k in self.config.keys():
            if k in transform_config.keys():
                final_config[k] = transform_config[k]

        final_config["vars"] = transform_config["vars"]

        result_path = self._transform(path=path, transform_config=final_config)

        return result_path

    @property
    def config(self):

        if self._merged_config is not None:
            return self._merged_config

        self._merged_config = {}
        for k, v in self.get_config_keys().items():
            if k in self._config.keys():
                self._merged_config[k] = self._config[k]
            else:
                self._merged_config[k] = v

        if "include" not in self._merged_config.keys():
            self._merged_config["include"] = self._config.get("include", ["*", ".*"])
        if "exclude" not in self._merged_config.keys():
            self._merged_config["exclude"] = self._config.get("exclude", [])

        return self._merged_config

    def get_config_keys(self) -> Dict:

        return {}

    @abstractmethod
    def _transform(self, path: str, transform_config: Dict = None) -> str:

        pass


class TransformException(FrklException):
    def __init__(
        self,
        *args,
        transformer_profile: "TransformProfileTing" = None,
        transformer: Transformer = None,
        **kwargs,
    ):

        self._transformer_profile = transformer_profile
        self._transformer = transformer

        super().__init__(*args, **kwargs)


class TransformProfile(object):
    def __init__(
        self,
        name: str,
        transformers_config: List,
        plugin_manager: TypistryPluginManager,
        meta: Dict[str, Any] = None,
    ):

        self._name = name
        self._transformers_config = transformers_config
        self._transformers: List[Transformer] = []

        for conf in self._transformers_config:

            t_type = conf["type"]
            plugin_cls: Type[Transformer] = plugin_manager.get_plugin(t_type)
            plugin_obj: Transformer = plugin_cls(**conf)
            self._transformers.append(plugin_obj)

    def transform(self, input_path: str, config: Dict[str, Any]) -> str:

        input_basename = os.path.basename(input_path)
        temp = tempfile.mkdtemp(
            prefix=f"transform_{self._name}_", dir=BRING_WORKSPACE_FOLDER
        )

        temp_input_path = os.path.join(temp, input_basename)
        shutil.copytree(input_path, temp_input_path)

        temp_input_path = input_path
        for transformer in self._transformers:

            new_input_path = transformer.transform(
                path=temp_input_path, transform_config=config
            )

            if new_input_path is None:
                log.info(
                    f"No path returned by transformer {transformer.name}, cancelling transform operation..."
                )
                shutil.rmtree(temp_input_path, ignore_errors=False)
                return None

            if new_input_path != temp_input_path:
                shutil.rmtree(temp_input_path, ignore_errors=False)
            temp_input_path = new_input_path

        return new_input_path


class TransformProfileTing(SimpleTing):
    def __init__(
        self, name: str, transformers_config: List, meta: Dict[str, Any] = None
    ):

        super().__init__(name=name, meta=meta)

        pm: TypistryPluginManager = self.tingistry.get_plugin_manager(
            "transformer", plugin_type="instance"
        )

        self._transform_profile = TransformProfile(
            name=self.full_name,
            transformers_config=transformers_config,
            plugin_manager=pm,
        )

    @property
    def transform_profile(self) -> TransformProfile:
        return self._transform_profile

    def provides(self) -> Dict[str, str]:

        return {}

    def retrieve(self, *value_names: str, **requirements) -> Dict[str, Any]:

        return {}
