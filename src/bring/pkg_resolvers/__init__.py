# -*- coding: utf-8 -*-
import json
import logging
import os
from abc import ABCMeta, abstractmethod
from collections import Sequence
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Tuple,
    Union,
)

import arrow
import httpx
from anyio import aopen
from bring.artefact_handlers import ArtefactHandler
from bring.defaults import (
    BRING_PKG_CACHE,
    DEFAULT_ARTEFACT_METADATA,
    PKG_RESOLVER_DEFAULTS,
)
from frtls.dicts import dict_merge, get_seeded_dict
from frtls.files import ensure_folder, generate_valid_filename
from frtls.strings import from_camel_case
from frtls.tasks import SerialTasksAsync, SingleTaskAsync, Task, Tasks
from frtls.types.typistry import TypistryPluginManager


if TYPE_CHECKING:
    from bring.context import BringContextTing

log = logging.getLogger("bring")


class PkgResolver(metaclass=ABCMeta):
    """Abstract base class which acts as an adapter to retrieve package information using the 'source' key in bring pkg metadata.


    """

    metadata_cache = {}

    @abstractmethod
    def _supports(self) -> Iterable[str]:
        """Return a list of package type this resolver supports (value of 'source.type')."""
        pass

    @abstractmethod
    def get_resolver_config(self) -> Mapping[str, Any]:
        """Return generic configuration information about this resolver.

        Supported keys (so far):
        - *metadata_max_age*: age of metadata in seconds that is condsidered valid (set to 0 to always invalidate/re-load metadata, -1 to never invalidate)
        """
        pass

    @abstractmethod
    def get_unique_source_id(
        self, source_details: Mapping, bring_context: "BringContextTing"
    ) -> str:
        """Return a calculated unique id for a package, derived from the contexts of the source details (and possibly the current context).

        This is used mainly for caching purposes.
        """
        pass

    @abstractmethod
    def get_artefact_defaults(self, source_details: Mapping) -> Mapping[str, Any]:
        pass

    async def get_seed_data(
        self, source_details: Mapping[str, Any], bring_context: "BringContextTing"
    ):
        """Overwrite to provide seed data for a pkg.

        This is mostly used for the 'bring-pkg' type, in order to retrieve parent metadata.
        Currently only 'info' and 'labels' keys are supported.
        """

        return None

    def check_pkg_metadata_valid(
        self,
        metadata: Optional[Mapping[str, Any]],
        source_details: Mapping[str, Any],
        bring_context: "BringContextTing",
        config: Optional[Mapping[str, Any]] = None,
    ) -> bool:
        """Check whether the provided metadata dictionary can be considered valid, or whether it needs to be reloaded.

        Args:
            - *metadata*: the metadata
            - *source_details*: source details of the package
            - *bring_context*: the current bring context
            - *config*: the resolver config, containing the 'metadata_max_age' key
        """

        if not metadata:
            return False

        if not metadata["metadata"].get("versions", None):
            return False

        if dict(metadata["source"]) != dict(source_details):
            return False

        if metadata["context"] != bring_context.full_name:
            return False

        if config is None:
            config = self.get_resolver_config()

        if config["metadata_max_age"] < 0:
            return True

        last_access = metadata["metadata"].get("metadata_check", None)
        if last_access is None:
            last_access = arrow.Arrow(1970, 1, 1)
        else:
            last_access = arrow.get(last_access)
        now = arrow.now()
        delta = now - last_access
        secs = delta.total_seconds()

        if secs < config["metadata_max_age"]:
            return True

        return False

    async def _get_cached_metadata(
        self,
        source_details: Mapping[str, Any],
        bring_context: "BringContextTing",
        config: Optional[Mapping[str, Any]] = None,
    ):
        """Return potentially cached (in memory) metadata for the package described by the provided details."""

        id = self.get_unique_source_id(source_details, bring_context)
        if not id:
            raise Exception("Unique source id can't be empty")

        metadata = PkgResolver.metadata_cache.setdefault(self.__class__, {}).get(
            id, None
        )

        # check whether we have the metadata in the global cache
        if self.check_pkg_metadata_valid(
            metadata, source_details, bring_context=bring_context, config=config
        ):
            return metadata["metadata"]

        # check whether the metadata is cached within the PkgResolver
        metadata = await self._get_pkg_metadata(
            source_details=source_details,
            bring_context=bring_context,
            config=config,
            cached_only=True,
        )
        if metadata is not None:
            PkgResolver.metadata_cache[self.__class__][id] = {
                "metadata": metadata,
                "source": source_details,
                "context": bring_context.full_name,
            }
            return metadata

        return None

    async def get_metadata_timestamp(
        self,
        source_details: Union[str, Mapping[str, Any]],
        bring_context: "BringContextTing",
    ) -> Optional[arrow.Arrow]:
        """Return the timestamp of the existing metadata for the package referenced by the provided details.

        Returns:
            the timestamp of the last metadata refresh, or 'None' if there is no metadata (yet)
        """

        if isinstance(source_details, str):
            _source_details = {"url": source_details}
        else:
            _source_details = source_details

        metadata = await self._get_cached_metadata(
            source_details=_source_details,
            bring_context=bring_context,
            config={"metadata_max_age": -1},
        )
        if metadata is None:
            return None

        last_access = metadata.get("metadata_check", None)
        if last_access is None:
            return None
        return arrow.get(last_access)

    async def get_pkg_metadata(
        self,
        source_details: Union[str, Mapping[str, Any]],
        bring_context: "BringContextTing",
        override_config: Optional[Mapping[str, Any]] = None,
    ) -> Mapping[str, Any]:
        """Return metadata of a bring package, specified via the provided source details and current context.

        Returns a dictionary with the following keys:

        *versions*: a list of dictionaries with the keys being package specific sets of variables that are combined to
                     denominate one version item, as well as a '_meta' key containing arbitrary metadata
        *aliases*: TO BE DONE
        *metadata_check*: timestamp string (incl. timezone) describing the date of the metadata check
        *args*: a mapping describing the available args that are required/optional to point to a specific version of a pkg
        """

        if isinstance(source_details, str):
            _source_details = {"url": source_details}
        else:
            _source_details = source_details

        config = get_seeded_dict(self.get_resolver_config(), override_config)

        metadata = await self._get_cached_metadata(
            source_details=_source_details, bring_context=bring_context, config=config
        )

        if metadata:
            return metadata

        # retrieve the metadata
        metadata = await self._get_pkg_metadata(
            source_details=_source_details,
            bring_context=bring_context,
            config=config,
            cached_only=True,
        )
        if metadata is not None:
            PkgResolver.metadata_cache[self.__class__][id] = {
                "metadata": metadata,
                "source": source_details,
                "context": bring_context.full_name,
            }
            return metadata

        metadata = await self._get_pkg_metadata(
            source_details=_source_details,
            bring_context=bring_context,
            config=config,
            cached_only=False,
        )
        PkgResolver.metadata_cache[self.__class__][id] = {
            "metadata": metadata,
            "source": source_details,
            "context": bring_context.full_name,
        }

        return metadata

    @abstractmethod
    async def _get_pkg_metadata(
        self,
        source_details: Mapping[str, Any],
        bring_context: "BringContextTing",
        config: Mapping[str, Any],
        cached_only=False,
    ) -> Mapping[str, Any]:
        """Concrete implementation of the method to retrieve the metadata for a specific package.

        This is called by 'get_pkg_metadata', if no in-memory cached version of the metadata can be found.
        """
        pass

    async def create_pkg_version_folder(
        self,
        vars: Mapping[str, Any],
        source_details: Mapping[str, Any],
        bring_context: "BringContextTing",
        override_config: Mapping[str, Any] = None,
    ) -> Tuple[str, Tasks]:

        metadata = await self.get_pkg_metadata(
            source_details=source_details,
            bring_context=bring_context,
            override_config=override_config,
        )

        version = self.find_version(vars=vars, metadata=metadata)

        path, retrieval_task = self._get_artefact_retrieval_task(
            version=version, source_details=source_details, bring_context=bring_context
        )

        artefact_details = get_seeded_dict(
            DEFAULT_ARTEFACT_METADATA,
            self.get_artefact_defaults(source_details),
            source_details.get("artefact", None),
        )
        art_type = artefact_details.get("type", None)
        if art_type is None:
            raise KeyError(
                f"No 'type' key in artefact details: {dict(artefact_details)}"
            )

        pm: TypistryPluginManager = bring_context._tingistry_obj.get_plugin_manager(
            "artefact_handler"
        )
        artefact_handler: ArtefactHandler = pm.get_plugin_for(art_type)
        id = self.get_unique_source_id(
            source_details=source_details, bring_context=bring_context
        )
        generate_valid_filename(id, sep="_")
        target_folder = ArtefactHandler.create_temp_dir_path(
            artefact_handler.__class__, leaf_folder_name=id
        )
        result_path, folder_task = await artefact_handler.provide_artefact_folder_tasks(
            target_folder=target_folder,
            artefact_path=path,
            artefact_details=artefact_details,
        )

        if retrieval_task is None and folder_task is None:
            _tasks = None
        else:
            _tasks: Tasks = SerialTasksAsync()
            if retrieval_task is not None:
                _tasks.add_task(retrieval_task)
            if folder_task is not None:
                _tasks.add_task(folder_task)

        return result_path, _tasks

    @abstractmethod
    def _get_artefact_retrieval_task(
        self,
        version: Mapping[str, Any],
        source_details: Mapping[str, Any],
        bring_context: "BringContextTing",
    ) -> Union[Task, Iterable[Task]]:

        pass

    # def calculate_unique_version_id(
    #     self, version: Mapping[str, str], source_details: Mapping[str, Any], bring_context: "BringContextTing"
    # ) -> str:
    #
    #     id = self.get_unique_source_id(source_details=source_details, bring_context=bring_context)
    #     if not id:
    #         raise Exception("Unique source id can't be empty")
    #
    #     for k in sorted(version):
    #         if k != "_meta":
    #             id = id + "_" + version[k]
    #     id = id + ".download"
    #
    #     return id

    def find_version(
        self, vars: Mapping[str, str], metadata: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Return details about one version item of a package, using the provided vars to find one (or the first) version that matches most/all of the provided vars.

        Args:
            - *vars*: User provided vars
            - *metadata*: the package metadata
        """

        aliases = metadata.get("aliases", {})
        # pkg_args = metadata.get("pkg_args", {})
        versions = metadata["versions"]

        # TODO: parse args

        vars_final = {}
        for k, v in vars.items():
            vars_final[k] = aliases.get(k, {}).get(v, v)

        matches = []
        for version in versions:

            match = True
            for k, v in version.items():
                if k == "_meta":
                    continue

                comp_v = vars_final.get(k, None)
                if not isinstance(comp_v, str) and isinstance(comp_v, Sequence):
                    temp_match = False
                    for c in comp_v:
                        if c == v:
                            temp_match = True
                            break
                    if not temp_match:
                        match = False
                        break
                else:

                    if comp_v != v:
                        match = False
                        break

            if match:
                matches.append(version)

        if not matches:
            return None

        if len(matches) == 1:
            return matches[0]

        # find the first 'exactest" match
        max_match = matches[0]
        for m in matches[1:]:
            if len(m) > len(max_match):
                max_match = m

        return max_match


class SimplePkgResolver(PkgResolver):
    def __init__(self, config: Optional[Dict[str, Any]] = None):

        self._cache_dir = os.path.join(
            BRING_PKG_CACHE, "resolvers", from_camel_case(self.__class__.__name__)
        )
        ensure_folder(self._cache_dir, mode=0o700)

        self._config: Mapping[str, Any] = get_seeded_dict(PKG_RESOLVER_DEFAULTS, config)

    def get_resolver_config(self) -> Mapping[str, Any]:

        return self._config

    @abstractmethod
    async def _process_pkg_versions(
        self, source_details: Mapping, bring_context: "BringContextTing"
    ) -> Mapping[str, Any]:
        """Process the provided source details, and retrieve a list of versions and other metadata related to the current state of the package.

        The resulting mapping has the following keys:

         - *versions*: (required) a list of version items for the package in question
         - *aliases*: (optional) a list of aliases (in the form of <ailas>: <actual value - e.g. x86_64: 64bit) that will be added to the allowed values of a pkg when searching for package version items
         - *args*: (optional) a seed schema to describe the full or partial arguments that are allowed/required when searching for package versions. This will be merged/overwritten with the value of a potential 'args' key in the 'source' definition of a package
        """
        pass

    def get_artefact_defaults(self, source_details: Dict) -> Dict[str, Any]:
        return {}

    async def _get_pkg_metadata(
        self,
        source_details: Mapping[str, Any],
        bring_context: "BringContextTing",
        config: Mapping[str, Any],
        cached_only=False,
    ) -> Optional[Mapping[str, Mapping]]:
        """Utility method that handles (external/non-in-memory) caching of metadata, as well as calculating the 'args' return parameter."""

        id = self.get_unique_source_id(source_details, bring_context=bring_context)
        if not id:
            raise Exception("Unique source id can't be empty")

        id = generate_valid_filename(id, sep="_")
        metadata_file = os.path.join(self._cache_dir, f"{id}.json")

        metadata = await self.get_metadata(metadata_file)
        if self.check_pkg_metadata_valid(
            metadata, source_details, bring_context=bring_context, config=config
        ):
            return metadata["metadata"]

        if cached_only:
            return None

        try:
            result: Mapping[str, Any] = await self._process_pkg_versions(
                source_details=source_details, bring_context=bring_context
            )
            versions: List[Mapping] = result["versions"]
            aliases: Mapping[str, str] = result.get("aliases", None)
            pkg_args: Mapping[str, Mapping] = result.get("args", None)

        except (Exception) as e:
            log.debug(f"Can't retrieve versions for pkg: {e}")
            log.debug(
                f"Error retrieving versions in resolver '{self.__class__.__name__}': {e}",
                exc_info=1,
            )
            raise e

        metadata["versions"] = versions

        if aliases is None:
            aliases = {}

        if "aliases" in source_details.keys():
            pkg_aliases = dict_merge(aliases, source_details["aliases"], copy_dct=False)
        else:
            pkg_aliases = aliases

        metadata["aliases"] = pkg_aliases

        args = await self.get_args(
            source_args=source_details.get("args", None),
            versions=versions,
            aliases=pkg_aliases,
            pkg_args=pkg_args,
        )
        metadata["pkg_args"] = args

        metadata["metadata_check"] = str(arrow.Arrow.now())

        await self.write_metadata(
            metadata_file, metadata, source_details, bring_context
        )

        return metadata

    async def get_args(
        self,
        source_args: Mapping[str, Any],
        versions: List[Mapping[str, Any]],
        aliases: Mapping[str, Dict[str, str]],
        pkg_args: Mapping[str, Any],
    ) -> Mapping[str, Mapping[str, Any]]:

        computed_args = {}
        for version in versions:
            for k in version.keys():
                if k == "_meta":
                    continue
                elif k in computed_args.keys():
                    val = version[k]
                    if val not in computed_args[k]["allowed"]:
                        computed_args[k]["allowed"].append(val)
                    continue

                computed_args[k] = {
                    "default": version[k],
                    "allowed": [version[k]],
                    "type": "string",
                }

        for var_name, alias_details in aliases.items():

            for alias, value in alias_details.items():
                if var_name in computed_args.keys():
                    if value not in computed_args[var_name]["allowed"]:
                        log.debug(
                            f"Alias '{alias}' does not have a corresponding value registered ('{value}'). Ignoring it..."
                        )
                        continue
                    if alias in computed_args[var_name]["allowed"]:
                        log.debug(
                            f"Alias '{alias}' (for value '{value}') already in possible values for key '{var_name}'. It'll be ignored if specified by the user."
                        )
                    else:
                        computed_args[var_name]["allowed"].append(alias)

        # now try to find keys that are not included in the first/latest version (most of the time there won't be any)
        args = get_seeded_dict(
            pkg_args, computed_args, source_args, merge_strategy="merge"
        )

        return args

    async def get_metadata(self, metadata_file: str):

        if not os.path.exists(metadata_file):
            return {}

        async with await aopen(metadata_file) as f:
            content = await f.read()
            metadata = json.loads(content)

        return metadata

    async def write_metadata(
        self,
        metadata_file: str,
        metadata: Mapping[str, Any],
        source: Mapping[str, Any],
        bring_context: "BringContextTing",
    ):

        data = {
            "metadata": metadata,
            "source": source,
            "context": bring_context.full_name,
        }
        async with await aopen(metadata_file, "w") as f:
            await f.write(json.dumps(data))


class HttpDownloadPkgResolver(SimplePkgResolver):
    def __init__(self, config: Optional[Mapping[str, Any]] = None):

        super().__init__(config=config)
        self._download_dir = os.path.join(self._cache_dir, "_downloads")
        ensure_folder(self._download_dir)

    def _get_artefact_retrieval_task(
        self,
        version: Mapping[str, Any],
        source_details: Mapping[str, Any],
        bring_context: "BringContextTing",
    ) -> Tuple[str, Optional[Task]]:

        download_url = self.get_download_url(
            version=version, source_details=source_details
        )

        # filename = self.calculate_unique_version_id(version=version, source_details=source_details)
        filename = version.get("_meta", {}).get("asset_name", None)
        if filename is None:
            filename = os.path.basename(download_url)

        target_path = os.path.join(self._download_dir, filename)

        if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
            log.debug(f"Cached file present, not downloading url: {download_url}")
            return target_path, None

        download_url = self.get_download_url(version, source_details)

        task = SingleTaskAsync(
            func=self.download_artefact,
            func_kwargs={"download_url": download_url, "target_path": target_path},
            msg=f"downloading '{download_url}'...",
            name="download task",
        )

        return target_path, task

    @abstractmethod
    def get_download_url(self, version: Dict[str, str], source_details: Dict[str, Any]):

        pass

    async def download_artefact(self, download_url: str, target_path: str):

        ensure_folder(os.path.dirname(target_path))
        log.debug(f"Downloading url: {download_url}")

        try:
            client = httpx.AsyncClient()
            async with await aopen(target_path, "wb") as f:
                async with client.stream("GET", download_url) as response:
                    async for chunk in response.aiter_bytes():
                        await f.write(chunk)
        finally:
            await client.aclose()

        return target_path
