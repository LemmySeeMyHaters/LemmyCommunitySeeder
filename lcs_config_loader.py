from dataclasses import dataclass
from enum import Enum

import toml


class SortType(Enum):
    ACTIVE = "Active"
    HOT = "Hot"
    NEW = "New"
    OLD = "Old"
    TOPDAY = "TopDay"
    TOPWEEK = "TopWeek"
    TOPMONTH = "TopMonth"
    TOPYEAR = "TopYear"
    TOPALL = "TopAll"
    MOSTCOMMENTS = "MostComments"
    NEWCOMMENTS = "NewComments"
    TOPHOUR = "TopHour"
    TOPSIXHOUR = "TopSixHour"
    TOPTWELVEHOUR = "TopTwelveHour"
    TOPTHREEMONTHS = "TopThreeMonths"
    TOPSIXMONTHS = "TopSixMonths"
    TOPNINEMONTHS = "TopNineMonths"


@dataclass
class LCSConfig:
    local_instance_url: str
    remote_instances: list[str]
    community_count: int
    community_sort_method: SortType
    skip_instances: list[str]
    minimum_monthly_active_users: int
    skip_communities: list[str]
    max_workers: int
    seconds_after_community_add: int
    skip_nsfw: bool

    @classmethod
    def load_config(cls) -> "LCSConfig":
        """
        Load Lemmy configuration from a TOML file.

        :return: An instance of the LemmyConfig class with configuration data.
        :rtype: LCSConfig

        """
        config_dict = toml.load("lcs_config.toml")
        lcs_config = cls(
            local_instance_url=config_dict.get("local_instance_url", ""),
            remote_instances=config_dict.get("remote_instances", []),
            community_count=config_dict.get("community_count", -1),
            community_sort_method=SortType(config_dict.get("community_sort_method", "Active")),
            skip_instances=config_dict.get("skip_instances", []),
            minimum_monthly_active_users=config_dict.get("minimum_monthly_active_users", 10),
            skip_communities=config_dict.get("skip_communities", []),
            max_workers=config_dict.get("max_workers", 2),
            seconds_after_community_add=config_dict.get("seconds_after_community_add", 5),
            skip_nsfw=config_dict.get("skip_nsfw", False),
        )
        return lcs_config
