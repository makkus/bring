# -*- coding: utf-8 -*-
import copy
import logging
import os
import shutil
import stat
import tempfile
from abc import ABCMeta, abstractmethod
from collections import Mapping
from typing import List, Union, Dict, Any, Iterable

from pathspec import PathSpec, patterns

from bring.defaults import BRING_WORKSPACE_FOLDER
from frtls.defaults import DEFAULT_EXCLUDE_DIRS
from frtls.exceptions import FrklException
from frtls.files import ensure_folder
from frtls.strings import from_camel_case
from frtls.types import Singleton, load_modules
from frtls.types.typistry import Typistry
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


class FileFilterTransformer(Transformer):
    def __init__(self, **config):

        super().__init__(**config)

    def get_config_keys(self) -> Dict:

        return {}

    def _transform(self, path: str, transform_config: Dict = None) -> str:

        matches = self.find_matches(path, transform_config=transform_config)

        if not matches:
            return None

        result = self.create_temp_dir()
        for m in matches:
            source = os.path.join(path, m)
            target = os.path.join(result, m)
            parent = os.path.dirname(target)
            ensure_folder(parent)
            shutil.copyfile(source, target)

        return result


class RenameTransformer(Transformer):
    def __init__(self, **config):

        super().__init__(**config)

    def get_config_keys(self) -> Dict:

        return {"rename": {}}

    def _transform(self, path: str, transform_config: Dict = None) -> str:

        rename = transform_config["rename"]
        if not rename:
            return path

        for source, target in rename.items():
            full_source = os.path.join(path, source)
            full_target = os.path.join(path, target)
            shutil.move(full_source, full_target)

        return path


class SetModeTransformer(Transformer):
    def __init__(self, **config):

        super().__init__(**config)

    def get_config_keys(self) -> Dict:

        return {
            "set_executable": self._config,
            "set_readable": None,
            "set_writeable": None,
        }

    def _transform(self, path: str, transform_config: Dict = None) -> str:

        matches = self.find_matches(path, transform_config, output_absolute_paths=True)

        set_executable = transform_config["set_executable"]
        set_readable = transform_config["set_readable"]
        set_writeable = transform_config["set_writeable"]

        for m in matches:
            st = os.stat(m)
            if set_executable is True:
                os.chmod(m, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
            elif set_executable is False:
                raise NotImplementedError()

            if set_readable in [True, False]:
                raise NotImplementedError()
            if set_writeable in [True, False]:
                raise NotImplementedError()

        return path


class TransformException(FrklException):
    def __init__(
        self,
        *args,
        transformer_profile: "TransformProfile" = None,
        transformer: Transformer = None,
        **kwargs,
    ):

        self._transformer_profile = transformer_profile
        self._transformer = transformer

        super().__init__(*args, **kwargs)


class MergeTransformer(Transformer):
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


class Transformistry(Typistry):

    __metaclass__ = Singleton
    initialized = False

    def __init__(self, preload_modules: Union[str, List[str]] = None):

        if preload_modules:
            load_modules(preload_modules)

        if not Transformistry.initialized:
            super().__init__(
                base_classes=[Transformer],
                key_formats=["underscore"],
                remove_postfixes="transformer",
            )
            Transformistry.initialized = True

    def create_transformer(self, transformer_config: Dict[str, Any]) -> Transformer:

        if isinstance(transformer_config, str):
            transformer_type = transformer_config
            transformer_config = {}
        elif isinstance(transformer_config, Mapping):
            transformer_type = transformer_config.pop("type", None)
            if transformer_type is None:
                raise KeyError(
                    "Can't create transformer object: Missing required key 'type'."
                )
        else:
            raise TypeError(
                f"Can't create transformer object, invalid type '{type(transformer_config)}': {transformer_config}"
            )

        t_cls = self.get_subclass(Transformer, transformer_type)
        t_obj = t_cls(**transformer_config)
        return t_obj


class TransformProfile(SimpleTing):
    def __init__(
        self, name: str, transformers_config: List, meta: Dict[str, Any] = None
    ):

        super().__init__(name=name, meta=meta)

        self._transformers_config = transformers_config
        self._transformers: List[Transformer] = []
        t = Transformistry()
        for conf in self._transformers_config:
            transformer = t.create_transformer(conf)
            self._transformers.append(transformer)

    def transform(self, input_path: str, config: Dict[str, Any]) -> str:

        input_basename = os.path.basename(input_path)
        temp = tempfile.mkdtemp(
            prefix=f"transform_{self.full_name}_", dir=BRING_WORKSPACE_FOLDER
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

    def provides(self) -> Dict[str, str]:

        return {}

    def retrieve(self, *value_names: str, **requirements) -> Dict[str, Any]:

        return {}
