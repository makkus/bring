# -*- coding: utf-8 -*-
import logging
import pathlib
import re
import time
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Sequence,
    Union,
)

import arrow
import httpx
from bring.defaults import BRING_RESOURCES_FOLDER
from bring.pkg_types import PkgType, PkgVersion
from bring.utils.github import get_data_from_github, get_list_data_from_github
from frkl.common.formats.serialize import serialize
from frkl.common.jinja_templating import process_string_template


DEFAULT_URL_REGEXES = [
    "https://github.com/.*/releases/download/v*(?P<version>.*)/.*-v*(?P=version)-(?P<arch>[^-]*)-(?P<os>[^.]*)\\..*$",
    "https://github.com/.*/releases/download/(?P<version>.*)/.*-(?P=version)-(?P<arch>[^-]*)-(?P<os>[^.]*)\\..*$",
    "https://github.com/.*/releases/download/v(?P<version>.*)/.*-(?P<arch>[^-]*)-(?P<os>[^.]*)$",
]


# "https://github.com/.*/releases/download/v(?P<version>.*)/.*-v(?P=version)-(?P<arch>[^-]*)-(?P<os>[^.]*)\\.(?P<type>.*)$"

log = logging.getLogger("bring")

GITHUB_PKG_DESC_TEMPLATE_FILE = (
    pathlib.Path(BRING_RESOURCES_FOLDER) / "pkg_desc_github_release.j2"
)


class GithubRelease(PkgType):
    """A package type that tracks GitHub release artefacts.

    To be able to get a list of all releases and their metadata, a package needs to specify the github user- and repo-names,
    as well as a regex to parse the release urls and compute the variables (version, architecture, os, etc.) involved to
    assemble a list of versions for a package.

    This is a barebones example for a *source* definition for the [fd](https://github.com/sharkdp/fd) application:

    ``` yaml
      source:
        type: github-release
        user_name: sharkdp
        repo_name: fd

        url_regex: 'https://github.com/.*/releases/download/v(?P<version>.*)/.*-v(?P=version)-(?P<arch>[^-]*)-(?P<os>[^.]*)\\..*$'
    ```
    More than one such regular expressions can be provided (in which case the value for *url_regex* should be a list), all matches for all regexes will be added to the resulting list.

    Most of the regexes for different packages look fairly similar, but unfortunately Github release-urls don't follow a standard, which
    makes it impossible to come up with one that can be used for all of them. *bring* comes with a default regex that works for quite
    a few Github projects (and almost for a lot of others). In fact, the regex in the example above is the default regex that will
    be used if no '*url_regex*' value is provided, and it so happens that it works for '*fd*' (which means we could have omitted it for that particular application).

    Nonetheless, whoever creates a new package manifest needs to manually verify whether the default regex works, and then adjust or create a totally different one if necessary.

    examples:
      - binaries.k3d
      - kubernetes.cert-manager


    """

    _plugin_name = "github_release"
    _plugin_supports = "github_release"

    last_github_limit_details: Optional[Mapping] = None

    @classmethod
    def get_github_limits(cls) -> Mapping[str, Any]:

        r = httpx.get("https://api.github.com/rate_limit")
        data = r.json()

        if not isinstance(data, Mapping):
            raise Exception(
                f"Unexpected return type '{type(data)}' when querying github limits: {data}"
            )

        details = {}
        details["limit"] = data["limit"]
        details["remaining"] = data["remaining"]
        details["reset_epoch"] = data["reset"]
        gmtime = time.gmtime(details["reset_epoch"])
        reset = arrow.get(gmtime)
        details["reset"] = reset

        cls.last_github_limit_details = details
        return details

    @classmethod
    def secs_to_github_limit_reset(cls) -> Optional[int]:

        if not cls.last_github_limit_details:
            cls.get_github_limits()

        now = arrow.now()
        delta = cls.last_github_limit_details["reset"] - now  # type: ignore
        secs = delta.total_seconds()
        return secs

    def __init__(self, **config: Any):

        self._github_username = None
        self._github_token = None
        self._github_username = config.get("github_username", None)
        self._github_token = config.get("github_access_token", None)

        super().__init__(**config)

    # def _supports(self) -> Iterable[str]:
    #
    #     return ["github-release"]

    def _get_unique_source_type_id(self, source_details: Mapping[str, Any]) -> str:

        github_user = source_details.get("user_name")
        repo_name = source_details.get("repo_name")

        artefact_name = source_details.get("artefact_name", "")

        if artefact_name:
            artefact_name = f"_{artefact_name}"

        return f"{github_user}_{repo_name}{artefact_name}"

    def get_artefact_mogrify(
        self, source_details: Mapping[str, Any], version: PkgVersion
    ) -> Union[Mapping, Iterable]:

        url: str = version.metadata.get("url")  # type: ignore

        match = False
        for ext in [".zip", ".gz", "tar.bz2"]:
            if url.endswith(ext):
                match = True
                break

        if match:
            return {"type": "archive"}
        else:
            return {"type": "file"}

    def get_args(self) -> Mapping[str, Any]:

        return {
            "user_name": {
                "type": "string",
                "required": True,
                "doc": "The github user name.",
            },
            "repo_name": {
                "type": "string",
                "required": True,
                "doc": "The github repo name.",
            },
            "url_regex": {
                "type": "string",
                "required": False,
                "doc": "The url regex to parse the release urls.",
            },
        }

    async def _process_pkg_versions(
        self, source_details: Mapping[str, Any]
    ) -> Mapping[str, Any]:

        github_user = source_details.get("user_name")
        repo_name = source_details.get("repo_name")
        request_path = f"/repos/{github_user}/{repo_name}/releases"

        releases = await get_list_data_from_github(
            path=request_path,
            github_username=self._github_username,
            github_token=self._github_token,
        )

        url_regexes: Iterable[str] = source_details.get("url_regex", None)
        if not url_regexes:
            url_regexes = DEFAULT_URL_REGEXES
        elif isinstance(url_regexes, str):
            url_regexes = [url_regexes]

        log.debug(f"Regexes for {github_user}/{repo_name}: {url_regexes}")

        result: List[PkgVersion] = []
        prereleases: List[PkgVersion] = []
        aliases: Dict[str, MutableMapping] = {}
        for release in releases:

            version_data = self.parse_release_data(release, url_regexes, aliases)
            if version_data:
                for vd in version_data:
                    _vers_obj = PkgVersion(**vd)
                    if vd.get("metadata", {}).get("prerelease", False):
                        # _v = PkgVersion()
                        prereleases.append(_vers_obj)
                    else:
                        result.append(_vers_obj)

        # args = copy.deepcopy(DEFAULT_ARGS_DICT)
        return {"versions": result + prereleases, "aliases": aliases}

    def parse_release_data(
        self,
        data: Mapping,
        url_regexes: Iterable[str],
        aliases: MutableMapping[str, MutableMapping],
    ) -> Sequence[Mapping[str, Any]]:

        result = []
        version = data["name"]
        prerelease = data["prerelease"]
        created_at = data["created_at"]
        # tarball_url = data["tarball_url"]
        # zipball_url = data["zipball_url"]

        meta = {
            "orig_version_name": version,
            "prerelease": prerelease,
            # "source_tarball_url": tarball_url,
            # "source_zipball_url": zipball_url,
            "release_date": created_at,
        }

        for asset in data["assets"]:
            browser_download_url = asset["browser_download_url"]
            log.debug(f"trying url: {browser_download_url}")
            vars = None
            for regex in url_regexes:
                match = re.search(regex, browser_download_url)
                if match is not None:
                    vars = match.groupdict()
                    break

            if vars is None:
                log.debug("No match")
                continue

            missing = []
            for k, v in vars.items():
                if v is None:
                    missing.append(k)
            for m in missing:
                vars.pop(m)
            log.debug(f"Matched vars: {vars}")

            if "version" in vars.keys():
                vers = vars["version"]
                if not prerelease:
                    if "stable" not in aliases.setdefault("version", {}).keys():
                        aliases["version"]["stable"] = vers
                    if "latest" not in aliases.setdefault("version", {}).keys():
                        aliases["version"]["latest"] = vers

                else:
                    if "pre-release" not in aliases.setdefault("version", {}).keys():
                        aliases["version"]["pre-release"] = vers

            asset_name = asset["name"]
            # content_type = asset["content_type"]
            size = asset["size"]

            _m = dict(meta)
            # _m["asset_name"] = asset_name
            # _m["content_type"] = content_type
            _m["size"] = size
            _m["url"] = browser_download_url
            _version_data = {
                "vars": vars,
                "metadata": _m,
                "steps": [
                    {
                        "type": "download",
                        "url": _m["url"],
                        "target_file_name": asset_name,
                    }
                ],
            }

            result.append(_version_data)

        return result

    async def create_pkg_desc_string(self, pkg_type: str, **kwargs: Any) -> str:

        arg_dict = self.get_args()

        args = self._arg_hive.create_record_arg(arg_dict, remove_required=True)
        validated_input: Dict[str, Any] = {}

        vars: Dict[str, Any] = {}
        for arg_name, arg in args.childs.items():

            value = kwargs.get(arg_name, None)
            if value is None:
                if arg.default:
                    default = arg.default
                    vars[arg_name] = arg.default
                else:
                    default = f"<{arg_name}_value>"
                validated_input[arg_name] = {
                    "value": default,
                    "arg": arg.doc,
                    "comment_out": True,
                    "required": arg.required,
                }
            else:
                validated = arg.validate(value)
                vars[arg_name] = validated
                validated_input[arg_name] = {
                    "value": validated,
                    "arg": arg.doc,
                    "required": arg.required,
                    "comment_out": False,
                }

        repl_dict: Dict[str, Any] = {
            "info_yaml": "",
            "args": validated_input,
            "pkg_type": pkg_type,
        }

        if "user_name" not in vars.keys() or "repo_name" not in vars.keys():

            result = process_string_template(
                GITHUB_PKG_DESC_TEMPLATE_FILE.read_text(),
                replacement_dict=repl_dict,
                jinja_env=self._jinja_env,
            )
            return result

        source_details = {
            "user_name": vars["user_name"],
            "repo_name": vars["repo_name"],
        }

        versions = None
        for r in DEFAULT_URL_REGEXES:
            source_details["url_regex"] = r
            md = await self.get_pkg_metadata(source_details)
            versions = md.versions
            if versions:
                break
            # TODO: check whether to switch os/arch

        if versions:
            validated_input.setdefault("url_regex", {})["value"] = r.replace(
                "\\", "\\\\"
            )
            validated_input.setdefault("url_regex", {})["comment_out"] = False

        data = await get_github_project_data(
            user=vars["user_name"], repo=vars["repo_name"]
        )

        info_yaml = serialize({"info": data["info"]}, format="yaml")
        repl_dict = {
            "info_yaml": info_yaml,
            "labels": data.get("labels", {}),
            "tags": data.get("tags", []),
            "args": validated_input,
            "pkg_type": pkg_type,
        }

        result = process_string_template(
            GITHUB_PKG_DESC_TEMPLATE_FILE.read_text(),
            replacement_dict=repl_dict,
            jinja_env=self._jinja_env,
        )

        return result


async def get_github_project_data(user: str, repo: str) -> Mapping[str, Any]:

    request_path = f"/repos/{user}/{repo}"

    data = await get_data_from_github(path=request_path)

    slug = data["description"]
    homepage = data["homepage"]
    if not homepage:
        homepage = data["html_url"]

    language = data.get("language", None)
    urls = {}
    url = data.get("downloads_url", None)
    if url:
        urls["downloads"] = url
    url = data["issues_url"].replace("{/number}", "")
    if url:
        urls["issues"] = url

    result = {
        "info": {"slug": slug, "homepage": homepage, "urls": urls},
    }

    if language:
        result.setdefault("labels", {})["language"] = language

    return result
