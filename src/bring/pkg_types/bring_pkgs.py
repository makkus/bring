# -*- coding: utf-8 -*-
from typing import Any, Iterable, Mapping, Optional

from bring.bring import Bring
from bring.mogrify import assemble_mogrifiers
from bring.pkg_index.index import BringIndexTing
from bring.pkg_index.pkg import PkgTing
from bring.pkg_types import SimplePkgType
from bring.utils import find_version, replace_var_aliases
from frtls.async_helpers import wrap_async_task
from frtls.exceptions import FrklException
from frtls.types.utils import is_instance_or_subclass


class BringPkgsResolver(SimplePkgType):
    """A package type that allows to create a single package out of two or more other packages.

    Currently, there are not many use-cases for this, so you can ignore this type. There are some more advanced use-cases
    that will be documented in the future.

    The value for the 'pkgs' variable is a list of dictionaries, with a required '*name*' value, as well as optional '*index*', '*vars*', and '*mogrify*' keys.

    Here's an example that 'installs' two different kubernetes manifest folders into a subfolder each:

    ``` yaml
        source:
          type: bring-pkgs

           pkgs:
             - name: kubernetes.ingress-nginx
               mogrify:
                 - type: move_to_subfolder
                   subfolder: ingress-nginx
             - name: kubernetes.cert-manager
               vars:
                 version: 0.13.0
               mogrify:
                 - type: move_to_subfolder
                   subfolder: cert-manager

    ```
    """

    _plugin_name: str = "bring_pkgs"

    def __init__(self, **config: Any):

        self._bring: Bring = config["bringistry"]
        super().__init__(**config)

    def _supports(self) -> Iterable[str]:

        return ["bring-pkg"]

    def get_args(self) -> Mapping[str, Any]:

        arg_dict = {
            "pkgs": {"type": "list", "required": True, "doc": "A list of packages."}
        }

        return arg_dict

    async def get_child_pkgs(
        self, source_details: Mapping[str, Any], bring_index: BringIndexTing
    ) -> Mapping[str, PkgTing]:

        pkgs = source_details["pkgs"]
        result = {}
        for pkg in pkgs:
            index = pkg.get("index", None)
            pkg_obj = await self.get_pkg(
                pkg["name"], bring_index=bring_index, pkg_index=index
            )
            result[pkg_obj.full_name] = pkg_obj

        return result

    async def get_seed_data(
        self, source_details: Mapping[str, Any], bring_index: BringIndexTing
    ) -> Mapping[str, Any]:
        """Overwrite to provide seed data for a pkg.

        This is mostly used for the 'bring-pkg' type, in order to retrieve parent metadata.
        """

        childs = {}
        child_pkgs = await self.get_child_pkgs(
            source_details=source_details, bring_index=bring_index
        )
        for pkg in child_pkgs.values():
            vals: Mapping[str, Any] = await pkg.get_values(  # type: ignore
                "info", resolve=True
            )
            info = vals["info"]
            childs[pkg.name] = info.get("slug", "n/a")

        return {"info": {"desc": childs}}

    async def get_pkg(
        self,
        pkg_name: str,
        bring_index: BringIndexTing,
        pkg_index: Optional[str] = None,
    ) -> PkgTing:

        if pkg_index is None:
            pkg_index = bring_index.full_name

        elif "." not in pkg_index:

            ctx = await self._bring.get_index(pkg_index)
            if ctx is None:
                ctx_names = self._bring.index_ids
                raise FrklException(
                    msg=f"Can't retrieve child pkg '{pkg_name}'.",
                    reason=f"Requested index '{pkg_index}' not among available indexes: {', '.join(ctx_names)}",
                )
            pkg_index = ctx.full_name

        ting_name = f"{pkg_index}.pkgs.{pkg_name}"

        ting = self._bring._tingistry_obj.get_ting(ting_name)
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

        pkgs = wrap_async_task(
            self.get_child_pkgs, source_details=source_details, bring_index=bring_index
        )
        pkg_names = sorted(pkgs.keys())

        return "_".join(pkg_names)

    async def _process_pkg_versions(
        self, source_details: Mapping, bring_index: BringIndexTing
    ) -> Mapping[str, Any]:

        pkgs = source_details["pkgs"]

        mogrifier_lists = []
        for pkg in pkgs:
            name = pkg["name"]
            vars = pkg.get("vars", {})
            index = pkg.get("index", None)

            pkg_obj = await self.get_pkg(name, bring_index=bring_index, pkg_index=index)
            vals: Mapping[str, Any] = await pkg_obj.get_values(  # type: ignore
                "metadata", resolve=True
            )
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
