# -*- coding: utf-8 -*-
from typing import Any, Iterable, Mapping, Optional

from bring.bring import Bring
from bring.context import BringContextTing
from bring.pkg import PkgTing
from bring.pkg_resolvers import SimplePkgResolver
from bring.utils import find_versions
from frtls.exceptions import FrklException
from frtls.types.utils import is_instance_or_subclass


class BringPkgResolver(SimplePkgResolver):

    _plugin_name: str = "bring_pkg"

    def __init__(self, config: Optional[Mapping[str, Any]]):

        if config is None:
            raise TypeError(
                "Can't create bring pkgs object. Invalid constructor arguments, need config map to access bringistry value."
            )

        self._bringistry: Bring = config["bringistry"]
        super().__init__(config=config)

    def _supports(self) -> Iterable[str]:

        return ["bring-pkg"]

    async def get_seed_data(
        self, source_details: Mapping[str, Any], bring_context: "BringContextTing"
    ):
        """Overwrite to provide seed data for a pkg.

        This is mostly used for the 'bring-pkg' type, in order to retrieve parent metadata.
        """

        parent = self.get_parent_pkg(
            source_dict=source_details, bring_context=bring_context
        )
        vals = await parent.get_values("info", "labels")

        return vals

    def get_parent_pkg(
        self, source_dict: Mapping[str, Any], bring_context: BringContextTing
    ) -> PkgTing:

        parent_name = source_dict["name"]
        parent_context = source_dict.get("context", None)
        if parent_context is None:
            parent_context = f"bring.contexts.{bring_context.name}"

        if parent_context != f"bring.contexts.{bring_context.name}":
            raise FrklException("BringPkg type does not support external contexts yet.")

        ting_name = f"{bring_context.full_name}.pkgs.{parent_name}"
        ting = self._bringistry.get_ting(ting_name)
        if ting is None:
            raise FrklException(
                msg="Can't resolve bring pkg.",
                reason=f"No parent pkg '{ting_name}' registered.",
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

        pkg = self.get_parent_pkg(source_details, bring_context)

        return pkg.full_name

    async def _process_pkg_versions(
        self, source_details: Mapping, bring_context: BringContextTing
    ) -> Mapping[str, Any]:

        pkg = self.get_parent_pkg(source_details, bring_context=bring_context)
        values: Mapping[str, Any] = await pkg.get_values(
            "metadata", resolve=True
        )  # type: ignore
        metadata = values["metadata"]

        vars = source_details.get("vars", {})
        versions = find_versions(vars, metadata)

        return {"versions": versions}
