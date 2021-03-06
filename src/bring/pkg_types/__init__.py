# -*- coding: utf-8 -*-
import copy
import logging
import os
import pathlib
import pickle
import shutil
import tempfile
from abc import ABCMeta, abstractmethod
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Union

import arrow
from anyio import aopen
from bring.defaults import (
    BRING_PKG_CACHE,
    BRING_RESOURCES_FOLDER,
    BRING_TEMP_CACHE,
    DEFAULT_ARGS_DICT,
    PKG_RESOLVER_DEFAULTS,
)
from deepdiff import DeepHash
from frkl.args.hive import ArgHive
from frkl.common.dicts import dict_merge, get_seeded_dict
from frkl.common.filesystem import ensure_folder
from frkl.common.jinja_templating import (
    get_global_jinja_env,
    get_template_schema,
    process_string_template,
    template_schema_to_args,
)
from frkl.common.regex import find_var_names_in_obj, replace_var_names_in_obj
from frkl.common.strings import from_camel_case
from jinja2 import Environment
from ruamel.yaml import YAML
from tzlocal import get_localzone


log = logging.getLogger("bring")

DEFAULT_PKG_DESC_TEMPLATE_FILE = pathlib.Path(BRING_RESOURCES_FOLDER) / "pkg_desc.j2"


class PkgVersion(object):
    def __init__(
        self,
        steps: Iterable[Mapping[str, Any]],
        vars: Mapping[str, Any],
        metadata: Optional[Mapping[str, Any]] = None,
    ):

        self._steps: List[Mapping[str, Any]] = list(steps)
        self._vars: Mapping[str, Any] = vars
        if metadata is None:
            metadata = {}
        self._metadata: Mapping[str, Any] = metadata

    @property
    def steps(self) -> List[Mapping[str, Any]]:
        return self._steps

    @steps.setter
    def steps(self, steps: Iterable[Mapping[str, Any]]):
        self._steps = list(steps)

    @property
    def vars(self) -> Mapping[str, Any]:
        return self._vars

    @property
    def metadata(self) -> Mapping[str, Any]:
        return self._metadata

    def to_dict(self) -> Mapping[str, Any]:

        result: Dict[str, Any] = {}
        result["steps"] = self._steps
        result["vars"] = self._vars
        result["metadata"] = self._metadata
        return result


class PkgMetadata(object):
    @classmethod
    def from_dict(cls, data: Mapping[str, Any]):

        source_details = data["source_details"]
        versions = data["versions"]
        version_list: List[PkgVersion] = []
        for v in versions:
            v_obj = PkgVersion(**v)
            version_list.append(v_obj)
        vars = data["vars"]
        _metadata_timestamp = data.get("metadata_timestamp", None)
        if _metadata_timestamp:
            _metadata_timestamp = arrow.get(_metadata_timestamp).datetime  # type: ignore
        aliases = data.get("aliases", None)

        return PkgMetadata(
            source_details=source_details,
            versions=version_list,
            vars=vars,
            metadata_timestamp=_metadata_timestamp,
            aliases=aliases,
        )

    def __init__(
        self,
        source_details: Mapping[str, Any],
        versions: Iterable[PkgVersion],
        vars: Mapping[str, Mapping[str, Any]],
        metadata_timestamp: Optional[datetime] = None,
        aliases: Optional[Mapping[str, Mapping[str, Any]]] = None,
    ):

        self._source_details: Mapping[str, Any] = source_details
        self._versions: Iterable[PkgVersion] = versions
        self._vars: Mapping[str, Mapping[str, Any]] = vars
        if metadata_timestamp is None:
            tz = get_localzone()
            metadata_timestamp = tz.localize(datetime.now(), is_dst=None)
        self._metadata_timestamp = metadata_timestamp
        if aliases is None:
            aliases = {}
        self._aliases: Mapping[str, Mapping[str, Any]] = aliases

    @property
    def source_details(self) -> Mapping[str, Any]:
        return self._source_details

    @property
    def versions(self) -> Iterable[PkgVersion]:
        return self._versions

    @property
    def vars(self) -> Mapping[str, Mapping[str, Any]]:
        return self._vars

    @property
    def metadata_timestamp(self) -> datetime:
        return self._metadata_timestamp

    @property
    def aliases(self) -> Mapping[str, Mapping[str, Any]]:
        return self._aliases

    def to_dict(self) -> Mapping[str, Any]:

        result: Dict[str, Any] = {}
        result["source_details"] = self._source_details
        result["versions"] = []
        for v in self.versions:
            result["versions"].append(v.to_dict())
        result["vars"] = self.vars
        result["metadata_timestamp"] = str(self.metadata_timestamp)
        result["aliases"] = self.aliases

        return result


def get_pkg_type_plugin_factory(arg_hive: ArgHive):

    _pkg_type_conf: MutableMapping[str, Any] = {}
    for k, v in os.environ.items():
        k = k.lower()
        if not k.startswith("bring_"):
            continue
        _pkg_type_conf[k[6:]] = v

    _pkg_type_conf["arg_hive"] = arg_hive

    return arg_hive.typistry.register_plugin_factory(
        "pkg_types", PkgType, singleton=True, use_existing=True, **_pkg_type_conf
    )


class PkgType(metaclass=ABCMeta):
    """Abstract base class which acts as an adapter to retrieve package information using the 'source' key in bring pkg metadata.
    """

    def __init__(self, arg_hive: ArgHive, **config: Any):
        """ The base class to inherit from to create package metadata of a certain type.

            Supported config keys (so far):
        - *metadata_max_age*: age of metadata in seconds that is condsidered valid (set to 0 to always invalidate/re-load metadata, -1 to never invalidate)
        """

        self._arg_hive: ArgHive = arg_hive
        self._cache_dir = os.path.join(
            BRING_PKG_CACHE, "resolvers", from_camel_case(self.__class__.__name__)
        )
        self._jinja_env_obj: Optional[Environment] = None
        ensure_folder(self._cache_dir, mode=0o700)

        self._config: Mapping[str, Any] = get_seeded_dict(PKG_RESOLVER_DEFAULTS, config)

    @property
    def resolver_config(self) -> Mapping[str, Any]:

        return self._config

    @abstractmethod
    def get_args(self) -> Mapping[str, Mapping[str, Any]]:
        """A dictionary describing which arguments are necessary to create a package of this type."""
        pass

    @property
    def _jinja_env(self) -> Environment:

        if self._jinja_env_obj is None:
            self._jinja_env_obj = get_global_jinja_env(env_type="default")
        return self._jinja_env_obj

    def get_unique_source_id(self, source_details: Mapping[str, Any]) -> str:
        """Return a calculated unique id for a package.

        Implement your own '_get_unique_type_source_id' method for a type specific, meaningful id.
        If that method is not overwritten, a 'deephash' of the source dictionary is used.

        This is used mainly for caching purposes.
        """

        return f"{from_camel_case(self.__class__.__name__)}_{self._get_unique_source_type_id(source_details=source_details)}"

    def _get_unique_source_type_id(self, source_details: Mapping[str, Any]):

        hashes = DeepHash(source_details)
        return hashes[source_details]

    async def get_seed_data(self, source_details: Mapping[str, Any]):
        """Overwrite to provide seed data for a pkg.

        This is mostly used for the 'bring-pkg' type, in order to retrieve parent metadata.
        Currently only 'info' and 'labels' keys are supported.
        """

        return None

    def _get_cache_path(
        self,
        source_details: Optional[Mapping[str, Any]] = None,
        _source_id: Optional[str] = None,
    ):

        if source_details is None and _source_id is None:
            raise Exception(
                "Can't compute cache path: need either 'source_details' or '_source_id'."
            )

        if _source_id is None:
            _source_id = self.get_unique_source_id(source_details)  # type: ignore

        path = os.path.join(self._cache_dir, _source_id)
        return path

    def _get_cache_details(
        self,
        source_details: Optional[Mapping[str, Any]] = None,
        _source_id: Optional[str] = None,
    ) -> Mapping[str, Any]:

        result: Dict[str, Any] = {}
        path = self._get_cache_path(
            source_details=source_details, _source_id=_source_id
        )
        result["path"] = path
        cache_file = pathlib.Path(path)

        if not cache_file.exists():
            result["exists"] = False
            return result

        if not cache_file.is_file():
            raise Exception(f"Cache file should be a file, but isn't: {path}")

        file_stat = cache_file.stat()
        file_size = file_stat.st_size
        if file_size == 0:
            os.unlink(cache_file)
            result["exists"] = False
            return result

        result["exists"] = True
        result["size"] = file_size
        modification_time = datetime.fromtimestamp(file_stat.st_mtime)
        tz = get_localzone()
        result["modified"] = tz.localize(modification_time)

        return result

    async def get_cached_metadata(
        self,
        source_details: Mapping[str, Any],
        override_config: Optional[Mapping[str, Any]],
        skip_validity_check: bool = False,
        _source_id: Optional[str] = None,
    ) -> Optional[PkgMetadata]:

        if not skip_validity_check:

            if not self.metadata_is_valid(
                source_details=source_details,
                _source_id=_source_id,
                override_config=override_config,
            ):
                return None

        details = self._get_cache_details(
            source_details=source_details, _source_id=_source_id
        )

        if not details["exists"]:
            return None

        path = details["path"]

        async with await aopen(path, "rb") as f:
            content = await f.read()

        metadata: PkgMetadata = pickle.loads(content)

        if metadata.source_details != source_details:
            return None

        return metadata

    def metadata_is_valid(
        self,
        source_details: Union[str, Mapping[str, Any]],
        override_config: Optional[Mapping[str, Any]] = None,
        _source_id: Optional[str] = None,
    ) -> bool:

        if isinstance(source_details, str):
            _source_details: Mapping[str, Any] = {"url": source_details}
        else:
            _source_details = source_details

        config = get_seeded_dict(self.resolver_config, override_config)

        cache_details = self._get_cache_details(
            source_details=_source_details, _source_id=_source_id  # type: ignore
        )

        if cache_details["exists"] is False:
            return False

        metadata_max_age = config["metadata_max_age"]
        modified = cache_details["modified"]
        file_date = arrow.get(modified)
        now = arrow.now(get_localzone())

        diff = now - file_date

        if diff.seconds > metadata_max_age:
            log.debug(f"Metadata cache expired for: {cache_details['path']}")

            return False

        # content: PkgMetadata = await self.get_cached_metadata(source_details=_source_details, config=override_config, _source_id=_source_id, skip_validity_check=True)
        #
        # if content.source_details != _source_details:
        #     return False

        return True

    async def get_pkg_metadata(
        self,
        source_details: Union[str, Mapping[str, Any]],
        override_config: Optional[Mapping[str, Any]] = None,
    ) -> PkgMetadata:
        """Return metadata of a bring package, specified via the provided source details and current index.

        If a string is provided as 'source_details', it'll be converted into a dict like: ``{"url": <source_details>}``.

        Args:
          source_details: the pkg-type specific details that are needed to create the package metadata
          override_config: optional configuration to adjust pkg metadata creation (e.g. cache invalidation, etc). overrides the default pkg-type config.

        Returns:
            PkgMetadata: the package metadata

        """

        if isinstance(source_details, str):
            _source_details: Mapping[str, Any] = {"url": source_details}
        else:
            _source_details = source_details

        source_id = self.get_unique_source_id(source_details=_source_details)

        cached_metadata = await self.get_cached_metadata(
            source_details=_source_details,
            override_config=override_config,
            _source_id=source_id,
        )

        if cached_metadata:
            return cached_metadata

        try:
            result: Mapping[str, Any] = await self._process_pkg_versions(
                source_details=_source_details
            )
            versions: Iterable[PkgVersion] = result["versions"]
            aliases: MutableMapping[str, str] = result.get("aliases", None)
            pkg_args: Mapping[str, Mapping] = result.get("args", None)
            default_args = copy.deepcopy(DEFAULT_ARGS_DICT)
            pkg_args = get_seeded_dict(default_args, pkg_args, merge_strategy="update")

        except (Exception) as e:
            log.debug(f"Can't retrieve versions for pkg: {e}")
            log.debug(
                f"Error retrieving versions in resolver '{self.__class__.__name__}': {e}",
                exc_info=True,
            )
            raise e

        metadata: Dict[str, Any] = {}
        metadata["versions"] = versions

        if aliases is None:
            aliases = {}

        if "aliases" in _source_details.keys():
            pkg_aliases = dict_merge(
                aliases, _source_details["aliases"], copy_dct=False
            )
        else:
            pkg_aliases = aliases

        metadata["aliases"] = pkg_aliases

        version_aliases = pkg_aliases.setdefault("version", {})

        for version in versions:

            if "version" in version.vars.keys() and "latest" not in version_aliases:
                version_aliases["latest"] = version.vars["version"]

            sam = _source_details.get("artefact", None)
            if sam:
                if isinstance(sam, str):
                    sam = {"type": sam}

                if isinstance(sam, Mapping):
                    version.steps.append(sam)
                else:
                    version.steps.extend(sam)
                continue

            if not hasattr(self, "get_artefact_mogrify"):
                continue

            vam = self.get_artefact_mogrify(_source_details, version)  # type: ignore

            if vam:
                if isinstance(vam, Mapping):
                    version.steps.append(vam)
                else:
                    version.steps.extend(vam)

        mogrifiers = _source_details.get("mogrify", None)
        if mogrifiers:
            for version in versions:
                if isinstance(mogrifiers, Mapping):
                    version.steps.append(mogrifiers)
                else:
                    version.steps.extend(mogrifiers)

        for version in versions:
            pkg_type_mogrifier = self.get_pkg_content_mogrify(_source_details, version)
            if pkg_type_mogrifier:
                if isinstance(pkg_type_mogrifier, Mapping):
                    version.steps.append(pkg_type_mogrifier)
                else:
                    raise NotImplementedError()
                    # version["_mogrify"]

        for version in versions:
            mog = version.steps
            # print(version)
            var_names = find_var_names_in_obj(mog)
            if var_names:
                vars = {}
                for k, v in version.vars.items():
                    if k.startswith("_"):
                        continue
                    vars[k] = v
                new_mog = replace_var_names_in_obj(mog, vars)
                # print(vars)
                # print(new_mog)
                version.steps = new_mog

        pkg_vars = await self.process_vars(
            source_args=_source_details.get("args", None),
            pkg_args=pkg_args,
            mogrifiers=mogrifiers,
            source_vars=_source_details.get("vars", None),
            versions=versions,  # type: ignore
            aliases=pkg_aliases,
        )
        metadata["vars"] = pkg_vars

        metadata["metadata_timestamp"] = str(arrow.Arrow.now())
        # await self.write_metadata(metadata_file, metadata, source_details, bring_index)

        pkg_md = PkgMetadata(source_details=_source_details, **metadata)

        await self.write_metadata(source_id=source_id, metadata=pkg_md)

        return pkg_md

    async def write_metadata(self, source_id: str, metadata: PkgMetadata):

        metadata_file = self._get_cache_path(_source_id=source_id)
        temp_file = tempfile.mkstemp(dir=BRING_TEMP_CACHE)[1]

        pickled = pickle.dumps(metadata)
        try:
            async with await aopen(temp_file, "wb") as f:
                await f.write(pickled)

            ensure_folder(os.path.dirname(metadata_file))
            shutil.move(temp_file, metadata_file)
        finally:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def get_pkg_content_mogrify(
        self, source_details: Mapping[str, Any], version: PkgVersion
    ) -> Optional[Union[Mapping, Iterable]]:

        content: Any = source_details.get("transform", None)
        pkg_vars = {}
        for k, v in version.vars.items():
            if k.startswith("_"):
                continue
            pkg_vars[k] = v

        pkg_content_mogrifier = {
            "type": "transform_folder",
            "pkg_vars": pkg_vars,
            "pkg_spec": content,
        }
        return pkg_content_mogrifier

    async def process_vars(
        self,
        source_args: Mapping[str, Any],
        pkg_args: Mapping[str, Any],
        mogrifiers: Union[Iterable, Mapping],
        source_vars: Mapping[str, Any],
        versions: List[PkgVersion],
        aliases: Mapping[str, Mapping[str, str]],
    ) -> Mapping[str, Any]:
        """Return the (remaining) args a user can specify to select a version or mogrify options.

        Source args can contain more arguments than will eventually be used/displayed to the user.

        Args:
            - *source_args*: dictionary of args to describe the type/schema of an argument
            - *pkg_args*: a dictionary of automatically created args by a specific resolver. Those will be used as base, but will be overwritten by anything in 'source_args'
            - *mogrifiers*: the 'mogrify' section of the pkg 'source'
            - *source_vars*: vars that are hardcoded in the 'source' section of a package, can also contain templates
            - *versions*: all avaailable versions of a package
            - *aliases*: a dictionary of value aliases that can be used by the user instead of the 'real' ones. Aliases are per arg name.

        Returns:
            a dictionary with 3 keys: args, version_vars, mogrify_vars
        """

        # calculate args to select version
        version_vars: MutableMapping[str, Mapping] = {}

        for version in versions:
            for k in version.vars.keys():
                if k.startswith("_"):
                    continue
                elif k in version_vars.keys():
                    val = version.vars[k]
                    if val not in version_vars[k]["allowed"]:
                        version_vars[k]["allowed"].append(val)
                    continue

                version_vars[k] = {
                    # "default": version[k],
                    "allowed": [version.vars[k]],
                    "type": "string",
                }
        # add aliases to 'allowed' values in version select args
        for var_name, alias_details in aliases.items():

            for alias, value in alias_details.items():
                if var_name in version_vars.keys():
                    if value not in version_vars[var_name]["allowed"]:
                        log.debug(
                            f"Alias '{alias}' does not have a corresponding value registered ('{value}'). Ignoring it..."
                        )
                        continue
                    if alias in version_vars[var_name]["allowed"]:
                        log.debug(
                            f"Alias '{alias}' (for value '{value}') already in possible values for key '{var_name}'. It'll be ignored if specified by the user."
                        )
                    else:
                        version_vars[var_name]["allowed"].append(alias)

        mogrify_vars: Mapping[str, Mapping]
        duplicates = {}
        if mogrifiers:
            template_schema = get_template_schema(mogrifiers)
            mogrify_vars = template_schema_to_args(template_schema)

            for k in mogrify_vars.keys():
                if k in version_vars.keys():
                    duplicates[k] = (mogrify_vars[k], version_vars[k])
        else:
            mogrify_vars = {}

        computed_vars = get_seeded_dict(
            mogrify_vars, version_vars, merge_strategy="update"
        )

        if source_vars is None:
            source_vars = {}

        required_keys = computed_vars.keys()
        # now try to find keys that are not included in the first/latest version (most of the time there won't be any)
        args = get_seeded_dict(
            pkg_args, computed_vars, source_args, merge_strategy="merge"
        )

        final_args = {}

        for k, v in args.items():
            if k in required_keys and k not in source_vars.keys():
                final_args[k] = v

        return {
            "args": final_args,
            "version_vars": version_vars,
            "mogrify_vars": mogrify_vars,
        }

    @abstractmethod
    async def _process_pkg_versions(
        self, source_details: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Process the provided source details, and retrieve a list of versions and other metadata related to the current state of the package.

        The resulting mapping has the following keys:

         - *versions*: (required) a list of version items for the package in question
         - *aliases*: (optional) a list of aliases (in the form of <ailas>: <actual value - e.g. x86_64: 64bit) that will be added to the allowed values of a pkg when searching for package version items
         - *args*: (optional) a seed schema to describe the full or partial arguments that are allowed/required when searching for package versions. This will be merged/overwritten with the value of a potential 'args' key in the 'source' definition of a package
        """
        pass

    async def create_pkg_desc_string(self, pkg_type: str, **kwargs: Any) -> str:

        arg_dict = self.get_args()

        args = self._arg_hive.create_record_arg(arg_dict, remove_required=True)
        validated_input: Dict[str, Any] = {}
        for arg_name, arg in args.childs.items():

            value = kwargs.get(arg_name, None)
            if value is None:
                if arg.default:
                    default = arg.default
                else:
                    default = f"<{arg_name}_value>"
                validated_input[arg_name] = {"value": default, "arg": arg.doc}
            else:
                validated = arg.validate(value)
                validated_input[arg_name] = {
                    "value": validated,
                    "arg": arg.doc,
                    "required": arg.required,
                }

        repl_dict = {
            "info": {},
            "args": validated_input,
            "pkg_type": pkg_type,
        }

        result = process_string_template(
            DEFAULT_PKG_DESC_TEMPLATE_FILE.read_text(),
            replacement_dict=repl_dict,
            jinja_env=self._jinja_env,
        )

        return result

    async def create_pkg_desc(
        self, pkg_type: str, **kwargs: Any
    ) -> MutableMapping[str, Any]:

        pkg_desc_str = await self.create_pkg_desc_string(pkg_type=pkg_type, **kwargs)
        yaml = YAML()
        pkg_desc = yaml.load(pkg_desc_str)
        return pkg_desc
