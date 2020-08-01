# -*- coding: utf-8 -*-
import gzip
import json
import logging
import os
import sys
from typing import Iterable

import asyncclick as click
from asyncclick.core import Argument, Option
from bring.bring import Bring
from bring.defaults import BRING_METADATA_FOLDER_NAME, DEFAULT_FOLDER_INDEX_NAME
from bring.interfaces.cli import console
from bring.pkg_index.utils import IndexDiff
from frkl.common.filesystem import ensure_folder


log = logging.getLogger("bring")


class BringExportIndexCommand(click.Command):
    def __init__(self, name: str, bring: Bring, **kwargs):

        self._bring: Bring = bring

        params = [
            Argument(
                ["index"],
                required=True,
                nargs=1,
                type=click.Path(
                    exists=True, file_okay=False, dir_okay=True, readable=True
                ),
                metavar="PATH_TO_INDEX_FOLDER",
            ),
            Option(
                ["--output-file", "-o"],
                required=False,
                metavar="PATH",
                help=f"the path to the index file, defaults to <index_folder>/.bring/{DEFAULT_FOLDER_INDEX_NAME}",
            ),
            Option(
                ["--force", "-f"],
                is_flag=True,
                help="overwrite existing, inconsistent index file",
            ),
            Option(
                ["--check", "-c"],
                help="check export for inconsistencies and errors",
                is_flag=True,
            ),
        ]
        super().__init__(name=name, callback=self.export_index, params=params, **kwargs)

    @click.pass_context
    async def export_index(
        ctx, self, output_file, index: str, force: bool, check: bool
    ):

        click.echo()

        _index = os.path.abspath(os.path.expanduser(index))
        if not os.path.isdir(os.path.realpath(_index)):
            click.echo(
                f"Can't export index '{index}': path does not exist or not a folder"
            )
            sys.exit(1)

        if output_file is None:
            _path = os.path.join(
                _index, BRING_METADATA_FOLDER_NAME, DEFAULT_FOLDER_INDEX_NAME
            )
        elif os.path.isdir(os.path.realpath(output_file)):
            click.echo(
                f"Can't write index file, specified output file is a folder: {output_file}"
            )
        else:
            _path = os.path.abspath(os.path.expanduser(output_file))

        index_obj = await self._bring.get_index(_index)
        exported_index = await index_obj.export_index()

        empty: bool = True
        for k in exported_index.keys():
            if not k.startswith("_"):
                empty = False
                break

        if empty:
            click.echo("Index does not contain any packages, doing nothing...")
            sys.exit(1)

        inconsistent: Iterable[str] = []
        if os.path.exists(_path):

            old_index = await self._bring.get_index(_path)
            diff = IndexDiff(old_index, index_obj)

            inconsistent = await diff.get_inconsistent_package_names()

            if inconsistent:

                if not force:
                    console.print(
                        f"[red bold]Can't update index, inconsistencies exist for package(s): {', '.join(sorted(inconsistent))}[/red bold]"
                    )
                else:
                    console.print(
                        f"Force update old index, even though are inconsistencies for packages: {', '.join(sorted(inconsistent))}"
                    )
            else:
                console.print("Older index file exists, no inconsistencies.")

            console.line()
            console.print("Details:")
            console.line()
            console.print(diff)
        else:
            console.print("No previous index file exists, writing new one...")
            ensure_folder(os.path.dirname(_path))

        if inconsistent and not force:
            sys.exit(1)

        if not check:
            console.line()
            console.print(f"Exporting index to file: {_path}")

            json_data = json.dumps(exported_index, indent=2) + "\n"
            json_bytes = json_data.encode("utf-8")

            with gzip.GzipFile(_path, "w") as f:
                f.write(json_bytes)
