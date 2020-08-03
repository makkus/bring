# -*- coding: utf-8 -*-
import logging
from typing import Any, List, Mapping, Optional

import gidgethub
import gidgethub.httpx
import httpx
from frkl.common.environment import get_var_value_from_env
from frkl.common.exceptions import FrklException
from gidgethub.abc import GitHubAPI
from gidgethub.sansio import RateLimit


log = logging.getLogger("bring")


async def get_data_from_github(
    path: str, github_username: Optional[str] = None, github_token: Optional[str] = None
) -> List[Mapping[str, Any]]:

    if not github_username:
        github_username = get_var_value_from_env(
            "github_username", prefixes=["freckles_", "bring_"]
        )
    if not github_token:
        github_token = get_var_value_from_env(
            "github_access_token", prefixes=["freckles_", "bring_"]
        )

    if not github_username:
        github_username = ""
    try:
        result_list: List[Mapping[str, Any]] = []
        async with httpx.AsyncClient() as client:
            gh: GitHubAPI = gidgethub.httpx.GitHubAPI(
                client, github_username, oauth_token=github_token
            )
            data = gh.getiter(path)
            async for i in data:
                result_list.append(i)

            if gh.rate_limit:
                log.debug(
                    f"github requests remaining: {gh.rate_limit.remaining}, reset: {gh.rate_limit.reset_datetime}"
                )

        return result_list
    except gidgethub.RateLimitExceeded as rle:
        rl: RateLimit = rle.rate_limit
        reason = f"Github rate limit exceeded (quota: {rle.rate_limit}, reset: {rl.reset_datetime})"
        if not github_username or not github_token:
            solution: Optional[
                str
            ] = "Set both 'github_user' and 'github_access_token' configuration values to make authenticated requests to GitHub and get a higher quota. You can do that via environment variables 'GITHUB_USERNAME' and 'GITHUB_ACCESS_TOKEN'."
        else:
            solution = f"Wait until your limit is reset: {rl.reset_datetime}"

        raise FrklException(
            "Could not retrieve data from Github.", reason=reason, solution=solution
        )
    except Exception as e:
        log.debug(f"Error with gitlab (accessing: {path})", exc_info=True)
        raise FrklException(
            msg=f"Can't retrieve data from github for: {path}", parent=e
        )
