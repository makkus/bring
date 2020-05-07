# -*- coding: utf-8 -*-
from typing import Any, Iterable, Mapping

from bring.bring import Bring
from bring.pkg_index import BringIndexTing
from bring.pkg_index.pkg import PkgTing
from bring.pkg_types import SimplePkgType
from bring.utils import find_versions, replace_var_aliases
from frtls.async_helpers import wrap_async_task
from frtls.exceptions import FrklException
from frtls.types.utils import is_instance_or_subclass


class BringPkgResolver(SimplePkgType):
    """A package type that creates a package that inherits from another, lower-level package in the same or another index.

    Currently, there are not many use-cases for this, so you can ignore this type. There are some more advanced use-cases
    that will be documented in the future.

    If no 'index_name' property is specified, it is assumed the package to use lives in the same index. Otherwise, the
    index must be valid in the configuration profile that is currently used.
    """

    _plugin_name: str = "bring_pkg"

    def __init__(self, **config: Any):

        self._bring: Bring = config["bringistry"]
        super().__init__(**config)

    def get_args(self) -> Mapping[str, Any]:

        arg_dict = {
            "name": {"type": "string", "required": True, "doc": "The package name."},
            "index": {"type": "string", "required": False, "doc": "The package index."},
        }

        return arg_dict

    def _supports(self) -> Iterable[str]:

        return ["bring-pkg"]

    async def get_seed_data(
        self, source_details: Mapping[str, Any], bring_index: "BringIndexTing"
    ):
        """Overwrite to provide seed data for a pkg.

        This is mostly used for the 'bring-pkg' type, in order to retrieve parent metadata.
        """

        parent = await self.get_parent_pkg(
            source_details=source_details, bring_index=bring_index
        )
        vals = await parent.get_values("info", "labels")

        return vals

    async def get_parent_pkg(
        self, source_details: Mapping[str, Any], bring_index: BringIndexTing
    ) -> PkgTing:

        pkg_name = source_details["name"]
        pkg_index = source_details.get("index", None)

        if pkg_index is None:
            pkg_index = bring_index

        elif "." not in pkg_index:

            ctx = await self._bring.get_index(pkg_index)
            if ctx is None:
                ctx_names = await self._bring.index_names
                raise FrklException(
                    msg=f"Can't retrieve child pkg '{pkg_name}'.",
                    reason=f"Requested index '{pkg_index}' not among available indexes: {', '.join(ctx_names)}",
                )
            pkg_index = ctx
        else:
            raise NotImplementedError()

        # ting_name = f"{pkg_index.full_name}.pkgs.{pkg_name}"

        ting = await pkg_index.get_pkg(pkg_name)
        ting_name = ting.full_name

        if ting is None:
            pkg_list = []
            for tn in self._bring._tingistry_obj.ting_names:
                # if '.pkgs.' in tn:
                pkg_list.append(tn)
            pkg_list_string = "\n  - ".join(pkg_list)
            raise FrklException(
                msg="Can't resolve bring pkg.",
                reason=f"Requested child pkg '{ting_name}' not among available pkgs:\n\n{pkg_list_string}",
            )

        if not is_instance_or_subclass(ting, PkgTing):
            raise FrklException(
                msg="Can't resolve bring pkg.",
                reason=f"Parent pkg '{ting_name}' does not sub-class the PkgTing class.",
            )

        return ting  # type: ignore

    def get_unique_source_id(
        self, source_details: Mapping, bring_index: BringIndexTing
    ) -> str:

        pkg = wrap_async_task(self.get_parent_pkg, source_details, bring_index)

        return pkg.full_name

    async def _process_pkg_versions(
        self, source_details: Mapping, bring_index: BringIndexTing
    ) -> Mapping[str, Any]:

        pkg = await self.get_parent_pkg(source_details, bring_index=bring_index)
        values: Mapping[str, Any] = await pkg.get_values(  # type: ignore
            "metadata", resolve=True
        )
        metadata = values["metadata"]

        vars = source_details.get("vars", {})
        vars = replace_var_aliases(vars=vars, metadata=metadata)

        versions = find_versions(vars, metadata, var_aliases_replaced=True)

        _versions = []
        for v in versions:
            _versions.append(v[0])

        return {"versions": _versions}
