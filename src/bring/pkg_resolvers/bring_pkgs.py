# -*- coding: utf-8 -*-
from typing import Any, Iterable, Mapping, Optional

from bring.bring import Bring
from bring.context import BringContextTing
from bring.mogrify import assemble_mogrifiers
from bring.pkg import PkgTing
from bring.pkg_resolvers import SimplePkgResolver
from bring.utils import find_version, replace_var_aliases
from frtls.exceptions import FrklException
from frtls.types.utils import is_instance_or_subclass


class BringPkgsResolver(SimplePkgResolver):

    _plugin_name: str = "bring_pkgs"

    def __init__(self, config: Optional[Mapping[str, Any]] = None):

        if config is None:
            raise TypeError(
                "Can't create bring pkgs object. Invalid constructor arguments, need config map to access bringistry value."
            )

        self._bringistry: Bring = config["bringistry"]
        super().__init__(config=config)

    def _supports(self) -> Iterable[str]:

        return ["bring-pkg"]

    def get_child_pkgs(
        self, source_details: Mapping[str, Any], bring_context: BringContextTing
    ) -> Mapping[str, PkgTing]:

        pkgs = source_details["pkgs"]
        result = {}
        for pkg in pkgs:
            context = pkg.get("context", None)
            pkg_obj = self.get_pkg(
                pkg["name"], bring_context=bring_context, pkg_context=context
            )
            result[pkg_obj.full_name] = pkg_obj

        return result

    async def get_seed_data(
        self, source_details: Mapping[str, Any], bring_context: BringContextTing
    ) -> Mapping[str, Any]:
        """Overwrite to provide seed data for a pkg.

        This is mostly used for the 'bring-pkg' type, in order to retrieve parent metadata.
        """

        childs = {}
        for pkg in self.get_child_pkgs(
            source_details=source_details, bring_context=bring_context
        ).values():
            vals: Mapping[str, Any] = await pkg.get_values(
                "info", resolve=True
            )  # type: ignore
            info = vals["info"]
            childs[pkg.name] = info.get("slug", "n/a")

        return {"info": {"desc": childs}}

    def get_pkg(
        self,
        pkg_name: str,
        bring_context: BringContextTing,
        pkg_context: Optional[str] = None,
    ) -> PkgTing:

        if pkg_context is None:
            pkg_context = bring_context.full_name

        elif "." not in pkg_context:

            ctx = self._bringistry.get_context(pkg_context)
            if ctx is None:
                raise FrklException(
                    msg=f"Can't retrieve child pkg '{pkg_name}'.",
                    reason=f"Requested context '{pkg_context}' not among available contexts: {', '.join(self._bringistry.contexts.keys())}",
                )
            pkg_context = ctx.full_name

        ting_name = f"{pkg_context}.pkgs.{pkg_name}"

        ting = self._bringistry.get_ting(ting_name)
        if ting is None:
            pkg_list = []
            for tn in self._bringistry.ting_names:
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

        pkgs = sorted(
            self.get_child_pkgs(
                source_details=source_details, bring_context=bring_context
            ).keys()
        )

        return "_".join(pkgs)

    async def _process_pkg_versions(
        self, source_details: Mapping, bring_context: BringContextTing
    ) -> Mapping[str, Any]:

        pkgs = source_details["pkgs"]

        mogrifier_lists = []
        for pkg in pkgs:
            name = pkg["name"]
            vars = pkg.get("vars", {})
            context = pkg.get("context", None)

            pkg_obj = self.get_pkg(
                name, bring_context=bring_context, pkg_context=context
            )
            vals: Mapping[str, Any] = await pkg_obj.get_values(
                "metadata", resolve=True
            )  # type: ignore
            metadata = vals["metadata"]

            vars = replace_var_aliases(vars=vars, metadata=metadata)
            version = find_version(
                vars=vars, metadata=metadata, var_aliases_replaced=True
            )

            if version is None:
                raise Exception(
                    f"Error when processing pkg '{name}'. Can't find version for vars: {dict(vars)}"
                )

            mogrifier_list = assemble_mogrifiers(
                version["_mogrify"],
                vars=vars,
                args=metadata["pkg_vars"]["mogrify_vars"],
                task_desc={"name": name},
            )

            item_mogrify = pkg.get("mogrify", None)
            if item_mogrify:
                mogrifier_list = mogrifier_list + item_mogrify

            mogrifier_lists.append(mogrifier_list)

        version = {"_mogrify": [mogrifier_lists]}

        return {"versions": [version]}
