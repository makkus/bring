# -*- coding: utf-8 -*-
from typing import Any, Dict, Mapping, MutableMapping, Optional, Union

import anyio
from anyio import create_task_group
from bring.config import ConfigTing
from tings.makers.file import TextFileTingMaker
from tings.ting import SimpleTing, TingMeta
from tings.ting.tings import SubscripTings
from tings.tingistry import Tingistry


class FolderConfigProfilesTing(SimpleTing):
    def __init__(
        self,
        name: str,
        meta: TingMeta,
        config_path: str,
        config_file_ext: str = "config",
    ):
        """A class to hold a set of ConfigTings, and gives access to them and their config dicts."""

        self._tingistry_obj: Tingistry = meta.tingistry

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
        self._init_lock = None

    async def _get_init_lock(self):

        if self._init_lock is None:
            self._init_lock = anyio.create_lock()
        return self._init_lock

    def requires(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        return {}

    def provides(self) -> Mapping[str, Union[str, Mapping[str, Any]]]:

        return {"profiles": "dict", "config_dicts": "dict"}

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        result: Dict[str, Any] = {}
        # config_input = requirements["config_input"]
        # _calculated = await self.calculate_config(config_input)

        if "profiles" in value_names:
            result["profiles"] = await self.get_config_profiles()

        if "config_dicts" in value_names:
            result["config_dicts"] = await self.get_config_dicts()

        return result

    async def get_config_profiles(
        self, update: bool = False
    ) -> Mapping[str, ConfigTing]:
        """Get all available config profiles."""

        async with await self._get_init_lock():
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

            profiles: MutableMapping[str, ConfigTing] = {
                k.split(".")[-1]: v  # type: ignore
                for k, v in self._profiles.childs.items()  # type: ignore
            }  # type: ignore

            return profiles

    async def get_config_dicts(
        self, update: bool = False
    ) -> Mapping[str, Mapping[str, Any]]:
        """Retrun the values of all available config profiles."""

        profiles = await self.get_config_profiles(update=update)

        result: Dict[str, Any] = {}

        async def get_config_dict(_p_name: str, _c_ting: ConfigTing):
            _dict = await _c_ting.get_value("config")
            result[_p_name] = _dict

        async with create_task_group() as tg:
            for profile_name, config_ting in profiles.items():
                await tg.spawn(get_config_dict, profile_name, config_ting)

        return result
