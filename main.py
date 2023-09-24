import asyncio
import math
import re
from csv import DictReader
from os import getenv
from typing import Optional, TypeVar, Awaitable, Iterator, Any

import httpx
import toml
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()
lemmy_jwt = None
lcs_config: dict[str, object] = {}


async def lemmy_auth() -> None:
    global lemmy_jwt
    """Authenticate with the Lemmy API using an aiohttp session.

    :param ClientSession httpx_session: The aiohttp ClientSession to use for the API request.

    :returns: None

    """
    auth = {"password": getenv("LEMMY_PASSWORD"), "totp_2fa_token": None, "username_or_email": getenv("LEMMY_USERNAME")}
    async with httpx.AsyncClient(headers={"accept": "application/json"}) as httpx_session:
        resp = await httpx_session.post(f"{lcs_config['local_instance_url']}/api/v3/user/login", json=auth)
        data = resp.json()
        lemmy_jwt = data.get("jwt")


async def get_instance_metadata(instance_url: str, httpx_client: httpx.AsyncClient) -> Optional[dict[str, Any]]:
    response = await httpx_client.get(f"{instance_url}/api/v3/site")
    return response.json() if response.status_code == 200 else None


async def get_community_local_id(ap_url: str, httpx_client: httpx.AsyncClient) -> Optional[int]:
    params = {"auth": lemmy_jwt, "q": ap_url}
    for _ in range(3):
        resp = await httpx_client.get("https://lemmykekw.xyz/api/v3/resolve_object", params=params)
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

                    if community_local_id is None:
                        continue

                    payload = {"follow": True, "community_id": community_local_id, "auth": lemmy_jwt}
                    resp = await client.post("https://lemmykekw.xyz/api/v3/community/follow", json=payload)
                    if resp.status_code == 200:
                        pagination_pbar.set_description(f"{pbar_desc} - Subscribed to {resp.json()['community_view']['community']['name']}")


markdown_url_pattern = re.compile(r"\[.*?\]\((.*?)\)")


def get_url_from_md(remote_instance: dict[str, Any]) -> Optional[str]:
    md_url: str = remote_instance["Instance"]
    result = markdown_url_pattern.search(md_url)
    return result.group(1) if result is not None else None


async def subscribe_instances() -> None:
    async with httpx.AsyncClient() as session:
        resp = await session.get("https://raw.githubusercontent.com/maltfield/awesome-lemmy-instances/main/awesome-lemmy-instances.csv")
        remote_instances = DictReader(resp.text.splitlines())

    instance_urls = filter(None, map(get_url_from_md, remote_instances))
    coroutine_pool = (subscribe_to_instance_communities(instance_url, idx) for idx, instance_url in enumerate(instance_urls))
    await limited_task_pool(max_concurrency=2, coroutines=coroutine_pool)


T = TypeVar("T")


async def limited_task_pool(max_concurrency: int, coroutines: Iterator[Awaitable[T]]) -> None:
    semaphore = asyncio.Semaphore(max_concurrency)

    async def worker(coroutine: Awaitable[T]) -> None:
        async with semaphore:
            await coroutine

    task_coroutines = (worker(coroutine) for coroutine in coroutines)
    await asyncio.gather(*task_coroutines)


async def main() -> None:
    global lcs_config

    with open("lcs_config.toml", "r") as fp:
        lcs_config = toml.load(fp)

    await lemmy_auth()
    await subscribe_instances()


if __name__ == "__main__":
    asyncio.run(main())
