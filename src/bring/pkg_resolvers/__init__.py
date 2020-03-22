# -*- coding: utf-8 -*-
import json
import logging
import os
from abc import ABCMeta, abstractmethod
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Type,
    Union,
)

import arrow
from anyio import aopen
from bring.defaults import BRING_PKG_CACHE, PKG_RESOLVER_DEFAULTS
from frtls.dicts import dict_merge, get_seeded_dict
from frtls.files import ensure_folder, generate_valid_filename
from frtls.strings import from_camel_case
from frtls.templating import get_template_schema, template_schema_to_args


if TYPE_CHECKING:
    from bring.context import BringContextTing

log = logging.getLogger("bring")


class PkgResolver(metaclass=ABCMeta):
    """Abstract base class which acts as an adapter to retrieve package information using the 'source' key in bring pkg metadata.


    """

    metadata_cache: Dict[Type, MutableMapping] = {}

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
        self, source_details: Mapping[str, Any], bring_context: "BringContextTing"
    ) -> str:
        """Return a calculated unique id for a package, derived from the contexts of the source details (and possibly the current context).

        This is used mainly for caching purposes.
        """
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
            - *freckops_bring_context*: the current bring context
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

        if config is None:
            config = {}

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
            _source_details: Mapping[str, Any] = {"url": source_details}
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

    async def metadata_is_valid(
        self,
        source_details: Union[str, Mapping[str, Any]],
        bring_context: "BringContextTing",
        override_config: Optional[Mapping[str, Any]] = None,
    ) -> bool:

        if isinstance(source_details, str):
            _source_details: Mapping[str, Any] = {"url": source_details}
        else:
            _source_details = source_details

        config = get_seeded_dict(self.get_resolver_config(), override_config)

        metadata = await self._get_cached_metadata(
            source_details=_source_details, bring_context=bring_context, config=config
        )

        if metadata:
            return True

        else:
            return False

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
        @param pkg_name:
        """

        if isinstance(source_details, str):
            _source_details: Mapping[str, Any] = {"url": source_details}
        else:
            _source_details = source_details

        config = get_seeded_dict(self.get_resolver_config(), override_config)

        metadata = await self._get_cached_metadata(
            source_details=_source_details, bring_context=bring_context, config=config
        )

        if metadata:
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
    ) -> Optional[Mapping[str, Any]]:
        """Concrete implementation of the method to retrieve the metadata for a specific package.

        This is called by 'get_pkg_metadata', if no in-memory cached version of the metadata can be found.

        Returns:
            the metadata, or None if 'cached_only' is specified and no cached metadata exists
        """
        pass


class SimplePkgResolver(PkgResolver):
    def __init__(self, config: Optional[Mapping[str, Any]] = None):

        self._cache_dir = os.path.join(
            BRING_PKG_CACHE, "resolvers", from_camel_case(self.__class__.__name__)
        )
        ensure_folder(self._cache_dir, mode=0o700)

        self._config: Mapping[str, Any] = get_seeded_dict(PKG_RESOLVER_DEFAULTS, config)

    def get_resolver_config(self) -> Mapping[str, Any]:

        return self._config

    @abstractmethod
    async def _process_pkg_versions(
        self, source_details: Mapping[str, Any], bring_context: "BringContextTing"
    ) -> Mapping[str, Any]:
        """Process the provided source details, and retrieve a list of versions and other metadata related to the current state of the package.

        The resulting mapping has the following keys:

         - *versions*: (required) a list of version items for the package in question
         - *aliases*: (optional) a list of aliases (in the form of <ailas>: <actual value - e.g. x86_64: 64bit) that will be added to the allowed values of a pkg when searching for package version items
         - *args*: (optional) a seed schema to describe the full or partial arguments that are allowed/required when searching for package versions. This will be merged/overwritten with the value of a potential 'args' key in the 'source' definition of a package
        """
        pass

    def get_artefact_mogrify(
        self, source_details: Mapping[str, Any], version: Mapping[str, Any]
    ) -> Optional[Union[Mapping, Iterable]]:
        """Return the mogrify instructions for a specific version item.

        Returns:
            either a single mogrify instructions, or several
        """
        return None

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
            aliases: MutableMapping[str, str] = result.get("aliases", None)
            pkg_args: Mapping[str, Mapping] = result.get("args", None)

        except (Exception) as e:
            log.debug(f"Can't retrieve versions for pkg: {e}")
            log.debug(
                f"Error retrieving versions in resolver '{self.__class__.__name__}': {e}",
                exc_info=True,
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

        for version in versions:

            sam = source_details.get("artefact", None)
            if sam:
                if isinstance(sam, Mapping):
                    version["_mogrify"].append(sam)
                else:
                    version["_mogrify"].extend(sam)
                continue

            if not hasattr(self, "get_artefact_mogrify"):
                continue

            vam = self.get_artefact_mogrify(source_details, version)

            if vam:
                if isinstance(vam, Mapping):
                    version["_mogrify"].append(vam)
                else:
                    version["_mogrify"].extend(vam)

        mogrifiers = source_details.get("mogrify", None)
        if mogrifiers:
            for version in versions:
                if isinstance(mogrifiers, Mapping):
                    version["_mogrify"].append(mogrifiers)
                else:
                    version["_mogrify"].extend(mogrifiers)

        pkg_vars = await self.process_vars(
            source_args=source_details.get("args", None),
            pkg_args=pkg_args,
            mogrifiers=mogrifiers,
            source_vars=source_details.get("vars", None),
            versions=versions,
            aliases=pkg_aliases,
        )
        metadata["pkg_vars"] = pkg_vars

        metadata["metadata_check"] = str(arrow.Arrow.now())

        await self.write_metadata(
            metadata_file, metadata, source_details, bring_context
        )

        return metadata

    async def process_vars(
        self,
        source_args: Mapping[str, Any],
        pkg_args: Mapping[str, Any],
        mogrifiers: Union[Iterable, Mapping],
        source_vars: Mapping[str, Any],
        versions: List[Mapping[str, Any]],
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
            for k in version.keys():
                if k == "_meta" or k == "_mogrify":
                    continue
                elif k in version_vars.keys():
                    val = version[k]
                    if val not in version_vars[k]["allowed"]:
                        version_vars[k]["allowed"].append(val)
                    continue

                version_vars[k] = {
                    "default": version[k],
                    "allowed": [version[k]],
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
