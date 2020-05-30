# -*- coding: utf-8 -*-
import collections
from typing import (
    TYPE_CHECKING,
    Any,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Union,
)

import anyio
from anyio import Lock
from bring.config import ConfigTing
from bring.config.folder_config import FolderConfigProfilesTing
from bring.defaults import (
    BRING_CONFIG_PROFILES_NAME,
    BRING_CORE_CONFIG,
    BRING_DEFAULT_CONFIG_PROFILE,
    BRING_TASKS_BASE_TOPIC,
)
from bring.merge_strategy import MergeStrategyArgType, MergeStrategyClickType
from frtls.args.hive import ArgHive
from frtls.async_helpers import wrap_async_task
from frtls.dicts import get_seeded_dict
from frtls.exceptions import FrklException
from frtls.introspection.pkg_env import AppEnvironment
from frtls.tasks.task_watcher import TaskWatchManager
from tings.tingistry import Tingistry


if TYPE_CHECKING:
    from bring.bring import Bring


def register_args(arg_hive: ArgHive):

    arg_hive.register_arg_type(
        arg=MergeStrategyArgType,
        id="merge_strategy",
        arg_type="dict",
        required=False,
        default=["bring"],
        click_type=MergeStrategyClickType,
    )


class BringConfig(object):
    """Wrapper to manage and access the configuration of a Bring instance."""

    def __init__(
        self,
        tingistry: Tingistry,
        name: Optional[str] = None
        # config_input: Optional[Iterable[Union[str, Mapping[str, Any]]]] = None,
    ):

        if name is None:
            name = "default"

        self._name = name
        self._tingistry_obj = tingistry

        register_args(self._tingistry_obj.arg_hive)

        self._config_contexts: FolderConfigProfilesTing = self._tingistry_obj.get_ting(  # type: ignore
            BRING_CONFIG_PROFILES_NAME, raise_exception=False
        )

        if self._config_contexts is None:
            # in case it wasn't created before, we use the default one
            self._tingistry_obj.register_prototing(
                **BRING_DEFAULT_CONFIG_PROFILE
            )  # type: ignore
            self._config_contexts: FolderConfigProfilesTing = self._tingistry_obj.get_ting(  # type: ignore
                BRING_CONFIG_PROFILES_NAME, raise_exception=True
            )

        self._config_input: Iterable[Union[str, Mapping[str, Any]]] = ["__init_dict__"]
        self._config_dict: Optional[Mapping[str, Any]] = None

        self._default_index_name: Optional[str] = None

        self._bring: Optional["Bring"] = None
        self._config_dict_lock: Optional[Lock] = None

        twm = AppEnvironment().get_global("task_watcher")
        if twm is None:
            twm = TaskWatchManager(typistry=self._tingistry_obj.typistry)
            AppEnvironment().set_global("task_watcher", twm)
        self._task_watch_manager: TaskWatchManager = twm
        self._task_watcher_ids: List[str] = []

    async def _get_config_dict_lock(self):

        # TODO: make this multithreaded?

        if self._config_dict_lock is None:
            self._config_dict_lock = anyio.create_lock()

        return self._config_dict_lock

    @property
    def name(self):

        return self._name

    def set_bring(self, bring: "Bring"):

        if self._bring is not None:
            raise Exception("Bring object already set for this config, this is a bug.")
        self._bring = bring
        self._bring.invalidate()

    def invalidate(self):

        self._config_dict = None

        if self._bring is not None:
            self._bring.invalidate()

    async def get_contexts(self, update: bool = False) -> Mapping[str, ConfigTing]:

        return await self._config_contexts.get_contexts(update=update)

    @property
    def config_input(self) -> Iterable[Union[str, Mapping[str, Any]]]:
        return self._config_input

    def set_config(self, *config_input: Union[str, Mapping[str, Any]]):

        _config_input: List[Union[str, Mapping[str, Any]]] = []
        # if not config_input or config_input[0] != "__init_dict__":
        #     _config_input.append("__init_dict__")

        for config in config_input:
            if config:
                _config_input.append(config)

        differs: bool = self._config_input != _config_input

        if differs:
            self._config_input = _config_input
            self.invalidate()

    async def calculate_config(
        self, _config_list: Iterable[Union[str, Mapping[str, Any]]]
    ) -> MutableMapping[str, Any]:

        # TODO: this could be made more efficient by only loading the config dicts that are required
        config_dicts: Mapping[
            str, Mapping[str, Any]
        ] = await self._config_contexts.get_config_dicts()

        result: List[Mapping[str, Any]] = []

        config_list: List[Union[str, Mapping[str, Any]]] = ["__init_dict__", "default"]
        config_list.extend(_config_list)

        for c in config_list:

            temp_dict: Optional[Mapping[str, Any]] = None
            if isinstance(c, str):
                if c == "__init_dict__":
                    temp_dict = BRING_CORE_CONFIG
                elif "=" in c:
                    k, v = c.split("=", maxsplit=1)
                    temp_dict = {k: v}

                elif c in config_dicts.keys():
                    temp_dict = config_dicts[c]

            elif isinstance(c, collections.Mapping):
                temp_dict = c

            if temp_dict is None:
                raise FrklException(
                    msg=f"Can't parse config item: {c}.",
                    reason="Invalid type or config option, must be either name of a config profile, a key/value pair (separated with '=', or a dict-like object.",
                )

            result.append(temp_dict)

        result_dict = get_seeded_dict(*result, merge_strategy="merge")

        return result_dict

    async def get_config_dict(self) -> Mapping[str, Any]:

        async with await self._get_config_dict_lock():
            if self._config_dict is not None:
                return self._config_dict

            profile_dict = await self.calculate_config(self.config_input)

            profile_dict.setdefault("default_index", None)

            if "defaults" not in profile_dict.keys():
                profile_dict["defaults"] = {}
            elif not isinstance(profile_dict["defaults"], collections.Mapping):
                raise FrklException(
                    f"Invalid config, 'defaults' value needs to be a mapping: {profile_dict['defaults']}"
                )

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

    def get_config_value(self, key: str) -> Any:

        if self._config_dict is None:
            wrap_async_task(self.get_config_dict)

        return self._config_dict.get(key, None)  # type: ignore

    async def get_config_value_async(self, key: str) -> Any:

        return (await self.get_config_dict()).get(key, None)

    async def get_default_index(self) -> str:

        config_dict = await self.get_config_dict()

        return config_dict["default_index"]

    def get_bring(self) -> "Bring":

        if self._bring is None:
            self._bring = self._tingistry_obj.create_singleting(  # type: ignore
                f"bring.{self.name}", "bring", bring_config=self
            )

        return self._bring  # type: ignore
