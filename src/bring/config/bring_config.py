# -*- coding: utf-8 -*-
import collections
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Union,
)

import anyio
from bring.config.folder_config import FolderConfigProfilesTing
from bring.defaults import (
    BRING_CONFIG_PROFILES_NAME,
    BRING_DEFAULT_CONFIG,
    BRING_DEFAULT_CONFIG_PROFILE,
    BRING_TASKS_BASE_TOPIC,
)
from bring.pkg_index import BringIndexTing
from bring.pkg_index.index_config import BringIndexConfig
from bring.system_info import get_current_system_info
from frtls.dicts import get_seeded_dict
from frtls.exceptions import FrklException
from frtls.introspection.pkg_env import AppEnvironment
from frtls.tasks.task_watcher import TaskWatchManager
from tings.tingistry import Tingistry


if TYPE_CHECKING:
    from bring.bring import Bring


class BringConfig(object):
    """Wrapper to manage and access the configuration of a Bring instance."""

    def __init__(
        self,
        tingistry: Tingistry,
        # config_input: Optional[Iterable[Union[str, Mapping[str, Any]]]] = None,
    ):

        self._tingistry_obj = tingistry

        self._config_profiles: FolderConfigProfilesTing = self._tingistry_obj.get_ting(  # type: ignore
            BRING_CONFIG_PROFILES_NAME, raise_exception=False
        )

        if self._config_profiles is None:
            # in case it wasn't created before, we use the default one
            self._tingistry_obj.register_prototing(
                **BRING_DEFAULT_CONFIG_PROFILE
            )  # type: ignore
            self._config_profiles: FolderConfigProfilesTing = self._tingistry_obj.get_ting(  # type: ignore
                BRING_CONFIG_PROFILES_NAME, raise_exception=True
            )

        self._config_input: Iterable[Union[str, Mapping[str, Any]]] = ["__init_dict__"]
        self._config_dict: Optional[Mapping[str, Any]] = None

        self._default_index_name: Optional[str] = None

        # self._extra_index_configs: List[BringIndexConfig] = []
        self._all_index_configs: Optional[Dict[str, BringIndexConfig]] = None
        self._bring: Optional["Bring"] = None
        # self._use_config_indexes: bool = True
        self._config_dict_lock = anyio.create_lock()

        twm = AppEnvironment().get_global("task_watcher")
        if twm is None:
            twm = TaskWatchManager(typistry=self._tingistry_obj.typistry)
            AppEnvironment().set_global("task_watcher", twm)
        self._task_watch_manager: TaskWatchManager = twm
        self._task_watcher_ids: List[str] = []

    def set_bring(self, bring: "Bring"):
        self._bring = bring

    def invalidate(self):

        self._config_dict = None
        # self._index_configs = None
        self._all_index_configs = None
        # self._auto_default_index_name = None

        if self._bring is not None:
            self._bring.invalidate()

    async def get_config_profiles(self, update: bool = False):

        return await self._config_profiles.get_config_profiles(update=update)

    @property
    def config_input(self) -> Iterable[Union[str, Mapping[str, Any]]]:
        return self._config_input

    @config_input.setter
    def config_input(
        self, config_input: Optional[Iterable[Union[str, Mapping[str, Any]]]]
    ):

        if config_input is None:
            config_input = []

        config_input = list(config_input)
        if not config_input or config_input[0] != "__init_dict__":
            config_input.insert(0, "__init_dict__")

        differs: bool = self._config_input != config_input
        self._config_input = config_input

        if differs:
            self.invalidate()

    async def calculate_config(
        self, config_list: Iterable[Union[str, Mapping[str, Any]]]
    ) -> MutableMapping[str, Any]:

        # TODO: this could be made more efficient by only loading the config dicts that are required
        config_dicts: Mapping[
            str, Mapping[str, Any]
        ] = await self._config_profiles.get_config_dicts()

        result: List[Mapping[str, Any]] = []

        for c in config_list:

            if isinstance(c, str):

                if c == "__init_dict__":
                    result.append(BRING_DEFAULT_CONFIG)
                    continue

                elif c not in config_dicts.keys():
                    raise FrklException(msg=f"No config profile '{c}'")

                result.append(config_dicts[c])
            else:
                result.append(c)

        result_dict = get_seeded_dict(*result, merge_strategy="merge")

        return result_dict

    async def get_config_dict(self) -> Mapping[str, Any]:

        async with self._config_dict_lock:
            if self._config_dict is not None:
                return self._config_dict

            profile_dict = await self.calculate_config(self.config_input)

            self._all_index_configs = {}
            default_index_name = self._default_index_name
            if default_index_name is None:
                default_index_name = profile_dict.get("default_index", None)

            profile_index_configs_first = None

            profile_index_configs = profile_dict.get("indexes", None)

            if not profile_index_configs:
                raise FrklException(
                    msg="Invalid configuration: no package indexes specified"
                )

            for index_config in profile_index_configs:

                index = BringIndexConfig.create(
                    tingistry_obj=self._tingistry_obj, init_data=index_config
                )
                # index = BringIndexConfig(
                #     tingistry_obj=self._tingistry_obj, init_data=index_config
                # )
                if index.name in self._all_index_configs.keys():
                    raise FrklException(
                        msg=f"Can't add index '{index.name}'",
                        reason="Duplicate index name.",
                    )
                if profile_index_configs_first is None:
                    profile_index_configs_first = index.name
                self._all_index_configs[index.name] = index

            if default_index_name is None:
                default_index_name = profile_index_configs_first

            exploded_index_configs = []
            for c in self._all_index_configs.values():
                config_dict = await c.to_dict()
                exploded_index_configs.append(config_dict)

            profile_dict["indexes"] = exploded_index_configs
            profile_dict["default_index"] = default_index_name

            if "defaults" not in profile_dict.keys():
                profile_dict["defaults"] = {}
            elif not isinstance(profile_dict["defaults"], collections.Mapping):
                raise FrklException(
                    f"Invalid config, 'defaults' value needs to be a mapping: {profile_dict['defaults']}"
                )

            if "vars" not in profile_dict["defaults"].keys():
                profile_dict["defaults"]["vars"] = {}
            elif not isinstance(profile_dict["defaults"]["vars"], collections.Mapping):
                raise FrklException(
                    f"Invalid config, 'vars' key in 'defaults' value needs to be a mapping: {profile_dict['defaults']['vars']}"
                )

            if profile_dict.get("add_sysinfo_to_default_vars", False):
                for k, v in get_current_system_info().items():
                    if k not in profile_dict["defaults"]["vars"].keys():
                        profile_dict["defaults"]["vars"][k] = v

            self._config_dict = profile_dict

            for watcher_id in self._task_watcher_ids:
                self._task_watch_manager.remove_watcher(watcher_id)

            self._task_watcher_ids.clear()
            task_log_config: Union[str, Mapping, Iterable] = self._config_dict.get(
                "task_log", []
            )

            if isinstance(task_log_config, (str, collections.Mapping)):
                task_log_config = [task_log_config]
            for tlc in task_log_config:
                if isinstance(tlc, str):
                    tlc = {"type": tlc, "base_topics": [BRING_TASKS_BASE_TOPIC]}

                id = self._task_watch_manager.add_watcher(tlc)
                self._task_watcher_ids.append(id)

            return self._config_dict

    async def get_default_index_name(self) -> str:

        config_dict = await self.get_config_dict()

        return config_dict["default_index"]

    async def set_default_index_name(self, index_name: str) -> None:

        acc = await self.get_all_index_configs()
        if index_name not in acc.keys():
            raise FrklException(
                msg=f"Can't set default index to '{index_name}'",
                reason="No index with that name.",
            )

        self._default_index_name = index_name
        self.invalidate()

    async def get_all_index_configs(self) -> Mapping[str, BringIndexConfig]:

        if self._all_index_configs is None:
            await self.get_config_dict()
        return self._all_index_configs  # type: ignore

    async def get_index_config(
        self, index_name: str, raise_exception: bool = True
    ) -> Optional[BringIndexConfig]:

        all_indexes = await self.get_all_index_configs()

        index_config = all_indexes.get(index_name, None)

        if index_config is None:
            if raise_exception:
                raise FrklException(
                    msg=f"Can't retrieve config for index '{index_name}'.",
                    reason="No index with that name registered.",
                )
            else:
                return None

        return index_config

    # async def ensure_index(
    #     self, index_config_string: str, set_default: bool = False
    # ) -> BringIndexConfig:
    #
    #     all_index_configs = await self.get_all_index_configs()
    #
    #     if index_config_string in all_index_configs.keys():
    #         await self.set_default_index_name(index_config_string)
    #         return all_index_configs[index_config_string]
    #
    #     _name: Optional[str]
    #     _config: str
    #     if "=" in index_config_string:
    #         _name, _config = index_config_string.split("=", maxsplit=1)
    #     else:
    #         _name = None
    #         _config = index_config_string
    #
    #     try:
    #         cc = await self.add_extra_index(
    #             index_config=_config, name=_name, set_default=set_default
    #         )
    #     except Exception as e:
    #         raise FrklException(
    #             msg=f"Invalid index data '{index_config_string}'.",
    #             reason="Not a valid index name, folder, or git url.",
    #             parent=e,
    #         )
    #
    #     return cc

    # async def add_extra_index(
    #     self,
    #     index_config: Union[str, Mapping[str, Any]],
    #     name: Optional[str] = None,
    #     set_default: bool = False,
    # ) -> BringIndexConfig:
    #     """Add an extra index to the current configuration."""
    #
    #     _index_config = BringIndexConfig(
    #         tingistry_obj=self._tingistry_obj, init_data=index_config
    #     )
    #     if name:
    #         _index_config.name = name
    #
    #     self._extra_index_configs.append(_index_config)
    #
    #     self.invalidate()
    #     await self.get_config_dict()
    #
    #     if set_default:
    #         await self.set_default_index_name(_index_config.name)
    #
    #     return _index_config

    async def get_index(self, index_name: str) -> BringIndexTing:

        index_config: BringIndexConfig = await self.get_index_config(
            index_name, raise_exception=True
        )  # type: ignore
        return await index_config.get_index()
