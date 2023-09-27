import asyncio
import math
import re
from csv import DictReader
from os import getenv
from typing import Optional, TypeVar, Awaitable, Any, Iterable, AsyncIterator

import httpx
from dotenv import load_dotenv
from tqdm import tqdm

from lcs_config_loader import LCSConfig

load_dotenv()
lemmy_jwt = None
lcs_config = LCSConfig.load_config()


async def lemmy_auth() -> None:
    """
    Authenticate with the Lemmy API using httpx AsyncClient.

    This function sends a POST request to the Lemmy API to authenticate a user using the provided
    environment variables for the username, password, and optional TOTP 2FA token. Upon successful
    authentication, it retrieves and stores the JWT token in the global variable `lemmy_jwt` for
    further API interactions.

    :returns: None

    """
    global lemmy_jwt
    auth = {"password": getenv("LEMMY_PASSWORD"), "totp_2fa_token": None, "username_or_email": getenv("LEMMY_USERNAME")}
    async with httpx.AsyncClient(headers={"accept": "application/json"}) as httpx_session:
        resp = await httpx_session.post(f"{lcs_config.local_instance_url}/api/v3/user/login", json=auth)
        data = resp.json()
        lemmy_jwt = data.get("jwt")


async def get_instance_metadata(instance_url: str, httpx_client: httpx.AsyncClient) -> Optional[dict[str, Any]]:
    response = await httpx_client.get(f"{instance_url}/api/v3/site")
    return response.json() if response.status_code == 200 else None


async def get_community_local_id(ap_url: str, httpx_client: httpx.AsyncClient) -> Optional[int]:
    params = {"auth": lemmy_jwt, "q": ap_url}
    for _ in range(3):
        resp = await httpx_client.get(f"{lcs_config.local_instance_url}/api/v3/resolve_object", params=params, timeout=None)
        if resp.status_code == 200:
            json_data = resp.json()
            community_id: int = json_data["community"]["community"]["id"]
            return community_id
    return None


async def subscribe_to_instance_communities(remote_instance_url: str, p_bar_position: int) -> None:
    async with httpx.AsyncClient(headers={"accept": "application/json"}) as client:
        instance_meta_data = await get_instance_metadata(remote_instance_url, client)
        if instance_meta_data is None:
            return None

        community_count = instance_meta_data["site_view"]["counts"]["communities"]
        params = httpx.QueryParams({"type_": "Local", "limit": 50})
        total_pages = math.ceil(community_count / 50)

        pbar_desc = f"{remote_instance_url}"
        with tqdm(range(1, total_pages), desc=pbar_desc, position=p_bar_position) as pagination_pbar:
            for pg_idx in pagination_pbar:
                params = params.set("page", pg_idx)
                resp = await client.get(f"{remote_instance_url}/api/v3/community/list", params=params)
                communities_subsection = resp.json()

                for community in communities_subsection["communities"]:
                    ap_url = f"!{community['community']['name']}@{remote_instance_url.removeprefix('https://')}"
                    community_local_id = await get_community_local_id(ap_url, client)

                    if community_local_id is None or ap_url in lcs_config.skip_communities:
                        continue

                    payload = {"follow": True, "community_id": community_local_id, "auth": lemmy_jwt}
                    resp = await client.post(f"{lcs_config.local_instance_url}/api/v3/community/follow", json=payload)
                    if resp.status_code == 200:
                        pagination_pbar.set_description(f"{pbar_desc} - Subscribed to {resp.json()['community_view']['community']['name']}")
                    await asyncio.sleep(lcs_config.seconds_after_community_add)


markdown_url_pattern = re.compile(r"\[.*?\]\((.*?)\)")


def get_url_from_md(remote_instances_dict: dict[str, str]) -> Optional[str]:
    """
    Extracts a URL from a given Markdown-formatted URL string.

    This function searches for a URL pattern within the input string `md_url` using a regular expression.
    If a match is found, it returns the first captured group of the matches, which is assumed to be the URL.
    If no match is found, it returns `None`.

    :param remote_instances_dict: A dict containing instance metadata.
    :type remote_instances_dict: dict[str, str]

    :return: The extracted URL or `None` if no URL is found.
    :rtype: Optional[str]
    """

    result = markdown_url_pattern.search(remote_instances_dict["Instance"])
    return result.group(1) if result is not None else None


async def fetch_instance_urls() -> AsyncIterator[str]:
    """
    Asynchronously fetches a list of Lemmy instance URLs from a remote server.

    Additionally, it checks if each instance meets the minimum user threshold
    specified in `lcs_config.minimum_user_threshold` and if it's included in the
    list of instances to skip (`lcs_config.skip_instances`).

    If `lcs_config.remote_instances` is provided, the minimum user threshold check
    and skip instances check are not performed.

    :return: An Async iterator of Lemmy instance URLs that meet the minimum user threshold
             and are not in the list of skipped instances.
    :rtype: AsyncIterator[str]

    """
    if lcs_config.remote_instances:
        for instance_url in lcs_config.remote_instances:
            yield instance_url
    else:
        async with httpx.AsyncClient() as session:
            resp = await session.get("https://raw.githubusercontent.com/maltfield/awesome-lemmy-instances/main/awesome-lemmy-instances.csv")
            remote_instances_dicts = DictReader(resp.text.splitlines())
            for remote_instance_dict in remote_instances_dicts:
                raw_url = get_url_from_md(remote_instance_dict)
                if raw_url is None or int(remote_instance_dict["Users"]) < lcs_config.minimum_monthly_active_users or raw_url in lcs_config.skip_instances:
                    continue
                yield raw_url


async def subscribe_instances() -> None:
    """
    Asynchronously subscribes to communities in Lemmy instances that meet the criteria.

    """
    remote_instances = fetch_instance_urls()
    coroutine_pool = []
    idx = 0
    async for instance_url in remote_instances:
        coroutine_pool.append(subscribe_to_instance_communities(instance_url, idx))
        idx += 1
    await limited_task_pool(max_concurrency=lcs_config.max_workers, coroutines=coroutine_pool)


T = TypeVar("T")


async def limited_task_pool(max_concurrency: int, coroutines: Iterable[Awaitable[T]]) -> None:
    """
    Execute a pool of asynchronous coroutines with a limited concurrency level.

    This function creates a pool of worker coroutines, where each worker executes the provided
    asynchronous coroutine.

    It limits the concurrency to a specified `max_concurrency` level by using a semaphore.

    :param max_concurrency: The maximum number of coroutines allowed running concurrently.
    :type max_concurrency: int

    :param coroutines: An iterable of asynchronous coroutines to be executed.
    :type coroutines: Iterable[Awaitable[T]]

    :returns: None
    """
    semaphore = asyncio.Semaphore(max_concurrency)

    async def worker(coroutine: Awaitable[T]) -> None:
        async with semaphore:
            await coroutine

    task_coroutines = (worker(coroutine) for coroutine in coroutines)
    await asyncio.gather(*task_coroutines)


async def main() -> None:
    await lemmy_auth()
    await subscribe_instances()


if __name__ == "__main__":
    asyncio.run(main())
