# -*- coding: utf-8 -*-
import logging
from typing import Any, List, Mapping, Optional

import gidgetlab
import gidgetlab.httpx
import httpx
from frkl.common.environment import get_var_value_from_env
from frkl.common.exceptions import FrklException
from gidgetlab.abc import GitLabAPI
from gidgetlab.sansio import RateLimit


log = logging.getLogger("bring")


async def get_data_from_gitlab(
    path: str, gitlab_username: Optional[str] = None, gitlab_token: Optional[str] = None
) -> List[Mapping[str, Any]]:

    if not gitlab_username:
        gitlab_username = get_var_value_from_env(
            "gitlab_username", prefixes=["freckles_", "bring_"]
        )
    if not gitlab_token:
        gitlab_token = get_var_value_from_env(
            "gitlab_access_token", prefixes=["freckles_", "bring_"]
        )

    if not gitlab_username:
        gitlab_username = ""
    try:

        result_list: List[Mapping[str, Any]] = []
        async with httpx.AsyncClient() as client:
            gh: GitLabAPI = gidgetlab.httpx.GitLabAPI(
                client, gitlab_username, access_token=gitlab_token
            )
            data = gh.getiter(path)
            async for i in data:
                result_list.append(i)

            if gh.rate_limit:
                log.debug(
                    f"gitlab requests remaining: {gh.rate_limit.remaining}, reset: {gh.rate_limit.reset_datetime}"
                )

        return result_list
    except gidgetlab.RateLimitExceeded as rle:
        rl: RateLimit = rle.rate_limit
        reason = f"Gitlab rate limit exceeded (quota: {rle.rate_limit}, reset: {rl.reset_datetime})"
        if not gitlab_username or not gitlab_token:
            solution: Optional[
                str
            ] = "Set both 'gitlab_user' and 'gitlab_access_token' configuration values to make authenticated requests to GitHub and get a higher quota. You can do that via environment variables 'GITLAB_USERNAME' and 'GITLAB_ACCESS_TOKEN'."
        else:
            solution = f"Wait until your limit is reset: {rl.reset_datetime}"

        raise FrklException(
            "Could not retrieve data from Github.", reason=reason, solution=solution
        )
    except Exception as e:
        log.debug(f"Error with gitlab (accessing: {path})", exc_info=True)
        raise FrklException(
            msg=f"Can't retrieve data from gitlab for: {path}", parent=e
        )
