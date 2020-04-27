# -*- coding: utf-8 -*-
import collections
import copy
import os
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
from anyio import create_task_group
from bring.context import BringContextTing
from bring.context.utils import create_context
from bring.defaults import (
    BRING_CONFIG_PROFILES_NAME,
    BRING_DEFAULT_CONFIG_PROFILE,
    BRING_DEFAULT_CONTEXTS,
)
from bring.system_info import get_current_system_info
from frtls.dicts import dict_merge, get_seeded_dict
from frtls.exceptions import FrklException
from frtls.strings import is_git_repo_url
from tings.makers.file import TextFileTingMaker
from tings.ting import SimpleTing
from tings.ting.inheriting import InheriTing
from tings.ting.tings import SubscripTings
from tings.tingistry import Tingistry


if TYPE_CHECKING:
    from bring.bring import Bring


class ConfigTing(InheriTing, SimpleTing):
    """Represents a config profile.

    Config profiles can inherit from other profiles, overwriting one or several of the parent key/value pairs.
    """

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
        """A class to hold a set of ConfigTings, and gives access to them and their config dicts."""

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
        self._init_lock = anyio.create_lock()

    @property
    def default_config(self):

        return self._default_config

    def requires(self) -> Mapping[str, str]:

        return {"config_input": "list"}

    def provides(self) -> Mapping[str, str]:

        return {"config_dict": "dict"}

    async def calculate_config(
        self, config: Iterable[Union[str, Mapping[str, Any]]]
    ) -> Mapping[str, Any]:

        profiles: Mapping[
            str, ConfigTing
        ] = await self.get_config_profiles(  # type: ignore
            update=False
        )  # type: ignore

        if config == ["default"]:
            return dict(self.default_config)

        result = [self.default_config]

        for c in config:

            if isinstance(c, str):

                profile_name = c
                if profile_name not in profiles.keys():
                    if profile_name == "default":
                        return {"config": self._default_config}
                    else:
                        raise FrklException(msg=f"No config profile '{profile_name}'")

                profile_dict = await profiles[profile_name].get_value("config")
                result.append(profile_dict)
            else:
                result.append(c)

        result_dict = get_seeded_dict(*result, merge_strategy="merge")

        return result_dict

    async def retrieve(self, *value_names: str, **requirements) -> Mapping[str, Any]:

        result = {}
        config_input = requirements["config_input"]
        _calculated = await self.calculate_config(config_input)
        result["config_dict"] = _calculated

        return result

    async def get_config_profiles(
        self, update: bool = False
    ) -> Mapping[str, ConfigTing]:
        """Get all available config profiles."""

        async with self._init_lock:
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
        """Retrun the values of all available config profiles."""

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


class BringContextConfig(object):
    @classmethod
    def auto_parse_config_string(
        cls, config_string: str, context_name: Optional[str] = None
    ) -> Dict[str, Any]:

        if config_string in BRING_DEFAULT_CONTEXTS.keys():
            _default_context: Mapping[str, Any] = BRING_DEFAULT_CONTEXTS[
                config_string
            ]  # type: ignore
            _init_data: Dict[str, Any] = dict(_default_context)
            _init_data["name"] = config_string
        elif config_string.endswith(".bx"):
            index_file_name = os.path.basename(config_string)
            _init_data = {
                "name": index_file_name[0:-3],
                "type": "index",
                "indexes": [config_string],
                "_name_autogenerated": True,
            }
        elif os.path.isdir(config_string) or is_git_repo_url(config_string):
            if config_string.endswith(os.path.sep):
                config_string = config_string[0:-1]
            if os.path.isdir(config_string):
                _name = os.path.basename(config_string)
            else:
                _name = config_string.split("/")[-1]

            if _name.endswith(".git"):
                _name = _name[0:-4]
            _init_data = {
                "name": _name,
                "type": "folder",
                "indexes": [config_string],
                "_name_autogenerated": True,
            }
        else:
            raise FrklException(
                msg=f"Can't create context for: {config_string}",
                reason="String is not a context alias, folder, or git url.",
            )

        if context_name is not None:
            _init_data["name"] = context_name
            _init_data["_name_generated"] = False

        return _init_data

    def __init__(
        self,
        tingistry_obj: Tingistry,
        init_data: Union[str, Mapping[str, Any]],
        global_defaults: Optional[Mapping[str, Any]] = None,
    ):

        self._tingistry_obj = tingistry_obj
        if isinstance(init_data, str):
            _init_data: Dict[str, Any] = BringContextConfig.auto_parse_config_string(
                config_string=init_data
            )
        else:
            if len(init_data) == 1 and list(init_data.keys())[0] not in [
                "name",
                "type",
            ]:
                context_name = list(init_data.keys())[0]
                config_string = init_data[context_name]
                _init_data = BringContextConfig.auto_parse_config_string(
                    config_string, context_name=context_name
                )
            else:
                _init_data = dict(init_data)

        self._name: str = _init_data.pop("name")
        self._type: str = _init_data.pop("type")
        self._name_autogenerated: bool = _init_data.pop("_name_autogenerated", False)
        self._init_data: Mapping[str, Any] = _init_data

        if global_defaults is None:
            global_defaults = {}
        self._global_defaults: MutableMapping[str, Any] = dict(global_defaults)

        defaults = self._init_data.get("defaults", {})
        if not self._global_defaults:
            _defaults: Mapping[str, Any] = defaults
        else:
            _defaults = dict_merge(self._global_defaults, defaults, copy_dct=False)
        self._init_data["defaults"] = _defaults

        if "vars" not in self._init_data["defaults"].keys():
            self._init_data["defaults"]["vars"] = {}
        elif not isinstance(self._init_data["defaults"]["vars"], collections.Mapping):
            raise FrklException(
                f"Invalid config, 'vars' key in 'defaults' context property needs to be a mapping: {self._init_data['defaults']['vars']}"
            )

        if self._init_data.get("add_sysinfo_to_default_vars", False):
            for k, v in get_current_system_info().items():
                if k not in self._init_data["defaults"]["vars"].keys():
                    self._init_data["defaults"]["vars"][k] = v
        self._context: Optional[BringContextTing] = None

    @property
    def name(self) -> str:

        return self._name

    @name.setter
    def name(self, name: str) -> None:

        if not self._name_autogenerated:
            raise FrklException(
                msg=f"Can't change name of context '{self._name}'.",
                reason="Name not autogenerated.",
            )

        self._name = name

    @property
    def type(self) -> str:

        return self._type

    @property
    def init_data(self) -> Mapping[str, Any]:

        return self._init_data

    def to_dict(self) -> Dict[str, Any]:

        result = dict(self._init_data)
        result["name"] = self.name
        result["type"] = self.type

        if self._name_autogenerated:
            result["_name_autogenerated"] = self._name_autogenerated

        return result

    async def get_context(self) -> BringContextTing:

        if self._context is None:
            self._context = await create_context(
                tingistry_obj=self._tingistry_obj, **self.to_dict()
            )
        return self._context


class BringConfig(object):
    """Wrapper to manage and access the configuration of a Bring instance."""

    def __init__(
        self,
        tingistry: Tingistry,
        config_input: Optional[Iterable[Union[str, Mapping[str, Any]]]] = None,
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

        # config & other mutable attributes
        if config_input is None:
            config_input = ["default"]
        self._config_input: Iterable[Union[str, Mapping[str, Any]]] = config_input
        self._config_dict: Optional[Mapping[str, Any]] = None

        self._default_context_name: Optional[str] = None

        self._extra_context_configs: List[BringContextConfig] = []
        self._all_context_configs: Optional[Dict[str, BringContextConfig]] = None
        self._bring: Optional["Bring"] = None
        self._use_config_contexts: bool = True

        self._config_dict_lock = anyio.create_lock()

    def set_bring(self, bring: "Bring"):
        self._bring = bring

    def invalidate(self):

        self._config_dict = None
        self._context_configs = None
        self._all_context_configs = None
        self._auto_default_context_name = None

        if self._bring is not None:
            self._bring.invalidate()

    @property
    def config_input(self) -> Iterable[Union[str, Mapping[str, Any]]]:
        return self._config_input

    @config_input.setter
    def config_input(
        self, config_input: Optional[Iterable[Union[str, Mapping[str, Any]]]]
    ):

        if config_input is None:
            config_input = ["default"]

        differs: bool = self._config_input != config_input
        self._config_input = config_input

        if differs:
            self.invalidate()

    @property
    def use_config_contexts(self) -> bool:

        return self._use_config_contexts

    @use_config_contexts.setter
    def use_config_contexts(self, use_config_contexts: bool) -> None:
        self._use_config_contexts = use_config_contexts
        self.invalidate()

    async def get_config_dict(self) -> Mapping[str, Any]:

        async with self._config_dict_lock:
            if self._config_dict is not None:
                return self._config_dict

            self._config_profiles.input.set_values(config_input=self._config_input)
            profile_dict = await self._config_profiles.get_value("config_dict")
            # TODO: check for error
            profile_dict = copy.deepcopy(profile_dict)

            self._all_context_configs = {}
            default_context_name = self._default_context_name
            if default_context_name is None:
                default_context_name = profile_dict.get("default_context", None)

            profile_context_configs_first = None

            if self._use_config_contexts:
                profile_context_configs = profile_dict.get("contexts", [])

                for context_config in profile_context_configs:

                    context = BringContextConfig(
                        tingistry_obj=self._tingistry_obj, init_data=context_config
                    )

                    if context.name in self._all_context_configs.keys():
                        raise FrklException(
                            msg=f"Can't add context '{context.name}'",
                            reason="Duplicate context name.",
                        )
                    if profile_context_configs_first is None:
                        profile_context_configs_first = context.name
                    self._all_context_configs[context.name] = context

            for ecc in self._extra_context_configs:

                if default_context_name is None:
                    default_context_name = ecc.name

                if ecc.name in self._all_context_configs.keys():

                    # if ecc._name_autogenerated:
                    #     new_name = find_free_name(ecc.name, current_names=self._all_context_configs.keys(), method="count", method_args={"start_count": 2})
                    #     ecc.name = new_name
                    # else:
                    raise FrklException(
                        msg=f"Can't add extra context '{ecc.name}'",
                        reason="Duplicate context name.",
                    )

                self._all_context_configs[ecc.name] = ecc

            if default_context_name is None:
                default_context_name = profile_context_configs_first

            exploded_context_configs = []
            for c in self._all_context_configs.values():
                exploded_context_configs.append(c.to_dict())

            profile_dict["contexts"] = exploded_context_configs
            profile_dict["default_context"] = default_context_name

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

            return self._config_dict

    async def get_default_context_name(self) -> str:

        config_dict = await self.get_config_dict()

        return config_dict["default_context"]

    async def set_default_context_name(self, context_name: str) -> None:

        acc = await self.get_all_context_configs()
        if context_name not in acc.keys():
            raise FrklException(
                msg=f"Can't set default context to '{context_name}'",
                reason="No context with that name.",
            )

        self._default_context_name = context_name
        self.invalidate()

    async def get_all_context_configs(self) -> Mapping[str, BringContextConfig]:

        if self._all_context_configs is None:
            await self.get_config_dict()
        return self._all_context_configs  # type: ignore

    async def get_context_config(
        self, context_name: str, raise_exception: bool = True
    ) -> Optional[BringContextConfig]:

        all_contexts = await self.get_all_context_configs()

        context_config = all_contexts.get(context_name, None)
        if context_config is None:
            if raise_exception:
                raise FrklException(
                    msg=f"Can't retrieve config for context '{context_name}'.",
                    reason="No context with that name registered.",
                )
            else:
                return None

        return context_config

    async def ensure_context(
        self, context_config_string: str, set_default: bool = False
    ) -> BringContextConfig:

        all_context_configs = await self.get_all_context_configs()

        if context_config_string in all_context_configs.keys():
            await self.set_default_context_name(context_config_string)
            return all_context_configs[context_config_string]

        _name: Optional[str]
        _config: str
        if "=" in context_config_string:
            _name, _config = context_config_string.split("=", maxsplit=1)
        else:
            _name = None
            _config = context_config_string

        try:
            cc = await self.add_extra_context(
                context_config=_config, name=_name, set_default=set_default
            )
        except Exception as e:
            raise FrklException(
                msg=f"Invalid context data '{context_config_string}'.",
                reason="Not a valid context name, folder, or git url.",
                parent=e,
            )
        return cc

    async def add_extra_context(
        self,
        context_config: Union[str, Mapping[str, Any]],
        name: Optional[str] = None,
        set_default: bool = False,
    ) -> BringContextConfig:
        """Add an extra context to the current configuration."""

        _context_config = BringContextConfig(
            tingistry_obj=self._tingistry_obj, init_data=context_config
        )
        if name:
            _context_config.name = name

        self._extra_context_configs.append(_context_config)

        self.invalidate()
        await self.get_config_dict()

        if set_default:
            await self.set_default_context_name(_context_config.name)

        return _context_config

    async def get_context(self, context_name: str) -> BringContextTing:

        context_config: BringContextConfig = await self.get_context_config(
            context_name, raise_exception=True
        )  # type: ignore
        return await context_config.get_context()
