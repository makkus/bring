# -*- coding: utf-8 -*-
import threading
from typing import Any, Dict, Mapping, Optional

from frtls.async_helpers import wrap_async_task
from frtls.dicts import dict_merge
from tings.makers.file import TextFileTingMaker
from tings.ting import SimpleTing
from tings.ting.inheriting import InheriTing
from tings.tingistry import Tingistry


class ConfigTing(InheriTing, SimpleTing):
    def __init__(
        self,
        name: str,
        parent_key: str = "parent",
        info_key: str = "info",
        meta: Optional[Mapping[str, Any]] = None,
    ):

        self._parent_key = parent_key
        self._info_key = info_key

        super().__init__(name=name, meta=meta)

    def provides(self) -> Dict[str, str]:

        return {
            self._parent_key: "string?",
            self._info_key: "string?",
            "config": "dict",
        }

    def requires(self) -> Dict[str, str]:

        return {"ting_dict": "dict"}

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        config_dict: Dict = dict(requirements["ting_dict"])

        parent = config_dict.pop(self._parent_key, None)
        info = config_dict.pop(self._info_key, None)

        result = {}
        if "config" in value_names:
            if "config" in requirements.keys():
                # still valid cache
                config = requirements["config"]
                result["config"] = config
            else:
                config = await self._get_config(config_dict, parent)
                result["config"] = config

        if self._info_key in value_names:
            result[self._info_key] = info
        if self._parent_key in value_names:
            result[self._parent_key] = parent

        return result

    async def _get_config(
        self, raw_config: Dict, parent: Optional[str] = None
    ) -> Dict[str, Any]:

        if not parent:
            return raw_config
        else:
            parent_vals = await self._get_values_from_ting(
                f"{self.namespace}.{parent}", "config"
            )
            config = parent_vals["config"]
            dict_merge(config, raw_config, copy_dct=False)
            return config


class FolderConfigProfilesTing(SimpleTing):
    def __init__(
        self,
        name: str,
        config_file_ext: str = "config",
        meta: Optional[Mapping[str, Any]] = None,
    ):

        if meta is None:
            raise Exception(
                "Can't create ting FolderConfigProfilesTing, 'meta' parameter not provided. This is a bug."
            )
        self._tingistry_obj: Tingistry = meta["tingistry"]

        super().__init__(name=name, meta=meta)

        self._maker_prototing_config = {
            "ting_class": "text_file_ting_maker",
            "prototing": "config_ting",
            "ting_name_strategy": "basename_no_ext",
            "ting_target_namespace": f"{self.full_name}.configs",
            "file_matchers": [
                {"type": "extension", "regex": f".*\\.{config_file_ext}"}
            ],
        }

        self._dynamic_config_maker: Optional[TextFileTingMaker] = None
        self._configs: Dict[str, ConfigTing] = {}

        self._initialized = False
        self._init_lock = threading.Lock()

    @property
    def dynamic_config_maker(self) -> TextFileTingMaker:

        if self._dynamic_config_maker is not None:
            return self._dynamic_config_maker

        dcm: TextFileTingMaker = self._tingistry_obj.create_singleting(  # type: ignore
            f"{self.full_name}.maker",
            prototing_name="internal.singletings.context_list",
            ting_class="subscrip_tings",
            prototing_factory="singleting",
            prototing="bring_dynamic_context_ting",
            subscription_namespace="bring.contexts.dynamic",
            ting_name=f"{self.full_name}.configs",
        )
        self._dynamic_config_maker = dcm
        return self._dynamic_config_maker

    def _init_sync(self):
        if self._initialized:
            return

        wrap_async_task(self._init, _raise_exception=True)

    async def _init(self):

        with self._init_lock:
            if self._initialized:
                return

            await self.dynamic_config_maker.sync()

            async def add_config(_cfg_name: str):
                pass

            configs = SubscripTings = self._tingistry_obj.get_ting()
