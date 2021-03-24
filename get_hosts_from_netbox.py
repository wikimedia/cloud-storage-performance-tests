#!/usr/bin/env python3
import os
import click
import requests
import json
from typing import Any, Dict, List, Optional
from enum import Enum, auto


DEFAULT_CONFIG_PATH = os.path.expanduser("~/.config/netbox/config.json")
DEFAULT_CONFIG = {
    "netbox_url": "https://netbox.local/api",
    "api_token": "IMADUMMYTOKEN",
}


class EntityType(Enum):
    devices = auto()


def device_to_str(
    device_dict: Dict[str, Any], domain: Optional[str] = None
) -> str:
    if domain is None:
        domain = f"{device_dict['site']['slug']}.wmnet"
    return f"{device_dict['name']}.{domain}"


ENTITY_TO_STR = {
    EntityType.devices: device_to_str,
}


def get_hosts(
    netbox_url: str,
    api_token: str,
    entity_type: EntityType,
    search_query: str,
) -> List[Dict[str, Any]]:
    response = requests.get(
        url=f"{netbox_url}/dcim/{entity_type.name}/",
        params={"q": search_query},
        headers={"Authorization": f"Token {api_token}"},
    )
    response.raise_for_status()
    return response.json()["results"]


def load_config_file(config_path: str = DEFAULT_CONFIG_PATH) -> Dict[str, str]:
    return json.load(open(config_path))


@click.command()
@click.option(
    "-c",
    "--config-file",
    default=DEFAULT_CONFIG_PATH,
    help="Path to the configuration file with the netbox settings.",
)
@click.option(
    "-e",
    "--entity",
    default=EntityType.devices.name,
    type=click.Choice([entity_type.name for entity_type in EntityType]),
    help="Type of entity to search for.",
)
@click.argument("search_query")
def cli(config_file: str, entity: str, search_query: str):
    config = load_config_file(config_path=config_file)
    entity_type = EntityType[entity]

    for device_dict in get_hosts(
        netbox_url=config["netbox_url"],
        api_token=config["api_token"],
        entity_type=entity_type,
        search_query=search_query,
    ):
        click.echo(ENTITY_TO_STR[entity_type](device_dict))


if __name__ == "__main__":
    cli()
