# -*- coding: utf-8 -*-
import threading
from typing import Any, Dict, Mapping, Optional

from anyio import create_task_group
from frtls.dicts import dict_merge
from frtls.exceptions import FrklException
from tings.makers.file import TextFileTingMaker
from tings.ting import SimpleTing
from tings.ting.inheriting import InheriTing
from tings.ting.tings import SubscripTings
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
        config_path: str,
        default_config: Mapping[str, Any],
        config_file_ext: str = "config",
        meta: Optional[Mapping[str, Any]] = None,
    ):

        if meta is None:
            raise Exception(
                "Can't create ting FolderConfigProfilesTing, 'meta' parameter not provided. This is a bug."
            )
        self._tingistry_obj: Tingistry = meta["tingistry"]

        self._default_config = default_config
        self._config_path = config_path
        self._config_file_ext = config_file_ext

        super().__init__(name=name, meta=meta)

        self._dynamic_config_maker: TextFileTingMaker = self._tingistry_obj.create_singleting(  # type: ignore
            name=f"{self.full_name}.maker",
            ting_class="text_file_ting_maker",
            prototing="config_ting",
            ting_name_strategy="basename_no_ext",
            ting_target_namespace=f"{self.full_name}.configs",
            file_matchers=[
                {"type": "extension", "regex": f".*\\.{self._config_file_ext}"}
            ],
        )
        self._dynamic_config_maker.add_base_paths(self._config_path)

        self._profiles: Optional[SubscripTings] = None

        self._initialized = False
        self._init_lock = threading.Lock()

    @property
    def default_config(self):

        return self._default_config

    def requires(self) -> Mapping[str, str]:

        return {"profile_name": "string", "update": "boolean?"}

    def provides(self) -> Mapping[str, str]:

        return {"config": "dict"}

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        profile = requirements["profile_name"]
        update = requirements.get("update", False)

        profiles: Mapping[
            str, ConfigTing
        ] = await self.get_config_profiles(  # type: ignore
            update=update
        )  # type: ignore

        if profile not in profiles.keys():
            if profile == "default":
                return {"config": self._default_config}
            else:
                raise FrklException(msg=f"No config profile '{profile}'")

        config = await profiles[profile].get_value("config")

        # result = get_seeded_dict(self._default_config, config, merge_strategy="merge")

        return {"config": config}

    async def get_config_profiles(
        self, update: bool = False
    ) -> Mapping[str, ConfigTing]:

        if self._profiles is None:

            self._profiles = self._tingistry_obj.create_singleting(  # type: ignore
                name=f"{self.full_name}.configs",
                ting_class="subscrip_tings",
                subscription_namespace=f"{self.full_name}.configs",
                prototing="config_ting",
            )
            await self._dynamic_config_maker.sync()
        else:
            if update:
                await self._dynamic_config_maker.sync()

        profiles: Mapping[str, ConfigTing] = {
            k.split(".")[-1]: v  # type: ignore
            for k, v in self._profiles.childs.items()  # type: ignore
        }  # type: ignore

        return profiles

    async def get_config_dicts(
        self, update: bool = False
    ) -> Mapping[str, Mapping[str, Any]]:

        profiles = await self.get_config_profiles(update=update)

        result: Dict[str, Any] = {}

        async def get_config_dict(_p_name: str, _c_ting: ConfigTing):
            _dict = await _c_ting.get_value("config")
            result[_p_name] = _dict

        async with create_task_group() as tg:
            for profile_name, config_ting in profiles.items():
                await tg.spawn(get_config_dict, profile_name, config_ting)

        if "default" not in result.keys():
            result["default"] = self._default_config

        return result
