# -*- coding: utf-8 -*-
from typing import Any, Iterable, Mapping, Optional

from bring.bring import Bring
from bring.context import BringContextTing
from bring.pkg import PkgTing
from bring.pkg_resolvers import SimplePkgResolver
from bring.utils import find_versions, replace_var_aliases
from frtls.async_helpers import wrap_async_task
from frtls.exceptions import FrklException
from frtls.types.utils import is_instance_or_subclass


class BringPkgResolver(SimplePkgResolver):

    _plugin_name: str = "bring_pkg"

    def __init__(self, config: Optional[Mapping[str, Any]]):

        if config is None:
            raise TypeError(
                "Can't create bring pkgs object. Invalid constructor arguments, need config map to access bringistry value."
            )

        self._bring: Bring = config["bringistry"]
        super().__init__(config=config)

    def _supports(self) -> Iterable[str]:

        return ["bring-pkg"]

    async def get_seed_data(
        self, source_details: Mapping[str, Any], bring_context: "BringContextTing"
    ):
        """Overwrite to provide seed data for a pkg.

        This is mostly used for the 'bring-pkg' type, in order to retrieve parent metadata.
        """

        parent = await self.get_parent_pkg(
            source_details=source_details, bring_context=bring_context
        )
        vals = await parent.get_values("info", "labels")

        return vals

    async def get_parent_pkg(
        self, source_details: Mapping[str, Any], bring_context: BringContextTing
    ) -> PkgTing:

        pkg_name = source_details["name"]
        pkg_context = source_details.get("context", None)

        if pkg_context is None:
            pkg_context = bring_context

        elif "." not in pkg_context:

            ctx = await self._bring.get_context(pkg_context)
            if ctx is None:
                ctx_names = await self._bring.context_names
                raise FrklException(
                    msg=f"Can't retrieve child pkg '{pkg_name}'.",
                    reason=f"Requested context '{pkg_context}' not among available contexts: {', '.join(ctx_names)}",
                )
            pkg_context = ctx
        else:
            raise NotImplementedError()

        # ting_name = f"{pkg_context.full_name}.pkgs.{pkg_name}"

        ting = await pkg_context.get_pkg(pkg_name)
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
        self, source_details: Mapping, bring_context: BringContextTing
    ) -> str:

        pkg = wrap_async_task(self.get_parent_pkg, source_details, bring_context)

        return pkg.full_name

    async def _process_pkg_versions(
        self, source_details: Mapping, bring_context: BringContextTing
    ) -> Mapping[str, Any]:

        pkg = await self.get_parent_pkg(source_details, bring_context=bring_context)
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
