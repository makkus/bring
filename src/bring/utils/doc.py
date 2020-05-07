# -*- coding: utf-8 -*-
from typing import Any, Dict, Mapping, Optional

from anyio import create_task_group
from bring.bring import Bring
from bring.pkg_types import PkgType
from frtls.doc import Doc
from frtls.exceptions import FrklException
from frtls.formats.output_formats import serialize


async def create_pkg_type_markdown_string_from_plugin_name(bring: Bring, name: str):

    pm = bring.typistry.get_plugin_manager(PkgType)
    doc = pm.get_plugin_doc(name)
    return create_pkg_type_markdown_string(bring=bring, plugin_doc=doc)


async def create_pkg_type_markdown_string(
    bring: Bring,
    plugin_doc: Doc,
    header_level: int = 2,
    add_description_header: bool = True,
):

    header = "#" * header_level

    plugin_doc.extract_metadata("examples")

    if plugin_doc.get_help(default=None, use_short_help=False):
        help_str = plugin_doc.get_help()
    else:
        help_str = "No description available."

    if add_description_header:
        markdown_string = f"{header} Description\n" + help_str + "\n\n"
    else:
        markdown_string = help_str + "\n\n"

    examples: Optional[Mapping[str, Any]] = plugin_doc.get_metadata_value("examples")
    if examples:
        examples_md: Dict[str, Mapping[str, Any]] = {}

        async def add_example(_example: str):
            pkg = await bring.get_pkg(_example)
            if pkg is None:
                raise FrklException(
                    msg=f"Can't add example for '{_example}'.",
                    reason="No such package available.",
                )
            vals: Mapping[str, Any] = await pkg.get_values(  # type: ignore
                "source", "info", resolve=True
            )  # type: ignore
            examples_md[_example] = vals

        async with create_task_group() as tg:

            for example in examples:
                await tg.spawn(add_example, example)

        markdown_string += f"{header} Examples\n\n"
        for example in examples:
            metadata = examples_md[example]
            markdown_string += f"Package: **{example}**\n\n"
            slug = metadata["info"].get("slug", "n/a")
            homepage = metadata["info"].get("homepage", "n/a")
            markdown_string += f"- desc: *{slug}*\n"
            markdown_string += f"- homepage: *{homepage}*\n\n"
            markdown_string += "- manifest:\n"
            source_yaml = serialize(
                {"source": metadata["source"]}, format="yaml", indent=6
            )
            markdown_string += f"``` yaml\n{source_yaml}\n```\n\n"

    return markdown_string
