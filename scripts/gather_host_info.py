#!/usr/bin/env python3
import click
import random
import json
import logging
import time
import datetime
import os
from functools import partial
from typing import Any, Callable, Dict, List, Optional
from enum import Enum
import subprocess

from generate_reports import StackLevel
from get_hosts_from_netbox import (
    load_config_file,
    get_hosts,
    device_to_str,
    EntityType,
)


class Site(Enum):
    codfw = "codfw1dev"
    eqiad = "eqiad1"


def check_call(command: List[str]) -> int:
    logging.debug(f"Running command {command}")
    return subprocess.check_call(command)


def get_random_netbox_host(
    hosts_query: str, site: Site, domain: Optional[str] = None
) -> List[str]:
    netbox_config = load_config_file()
    all_matching_hosts = [
        device_to_str(device_dict, domain=domain)
        for device_dict in get_hosts(
            netbox_url=netbox_config["netbox_url"],
            api_token=netbox_config["api_token"],
            entity_type=EntityType.devices,
            search_query=hosts_query,
        )
        if device_dict["site"]["slug"] == site.name
    ]
    if len(all_matching_hosts) < 1:
        raise Exception(
            f"Unable to get enough hosts matching '{hosts_query}' for site "
            f"'{site.name}', need 1 but got "
            f"{len(all_matching_hosts)}."
        )
    return random.choice(all_matching_hosts)


def get_os_run(
    project: str, site: Site
) -> Callable[List[str], Dict[str, Any]]:
    control_host = get_random_netbox_host(
        hosts_query="cloudcontrol",
        site=site,
        # cloudcontrol hosts are only accessible through the wikimedia.org
        # domain
        domain="wikimedia.org",
    )

    def _run_os(*command_args):
        command = [
            "ssh",
            control_host,
            "sudo",
            "wmcs-openstack",
            "--os-project-id",
            project,
            *command_args,
            "-f",
            "json",
        ]
        logging.debug(f"Running command {command}")
        response = json.loads(subprocess.check_output(command).decode())
        return response

    return _run_os


def get_performance_vm(site: Site) -> List[str]:
    performance_vm_name = "performance-test"
    performance_project = "testlabs"
    os_run = get_os_run(project=performance_project, site=site)
    performance_vm_info = next(
        (
            vm_info["Name"]
            for vm_info in os_run("server", "list")
            if vm_info["Name"] == performance_vm_name
        ),
        None,
    )
    performance_vm_fqdn = (
        f"{performance_vm_name}.{performance_project}.{site.value}"
        ".wikimedia.cloud"
    )

    if performance_vm_info is None:
        logging.info(
            f"Unable to find performance VM ({performance_vm_name}) under "
            f"project {performance_project}, on site {site.value}, creating..."
        )
        os_run(
            "server",
            "create",
            performance_vm_name,
            "--flavor",
            "g2.cores1.ram2.disk20",
            "--image",
            "debian-10.0-buster",
            "--network",
            "lan-flat-cloudinstances2b",
            "--wait",
        )

        waitfor = 60 * 15  # 15 minutes
        ran_puppet = False
        start_time = time.time()
        while not ran_puppet:
            try:
                check_call(
                    [
                        "ssh",
                        performance_vm_fqdn,
                        "sudo",
                        "run-puppet-agent",
                    ]
                )
            except Exception:
                cur_time = time.time()
                if (cur_time - start_time) > waitfor:
                    logging.error(
                        f"Unable to spin up the vm {performance_vm_name} "
                        f"(project: {performance_project}, "
                        f"site: {site.name}), timed out waiting for puppet to "
                        "run."
                    )
                    raise

                logging.info(
                    f"Waiting for the VM {performance_vm_fqdn} to come online "
                    "and do a full puppet run..."
                )
                time.sleep(60)
                continue

            ran_puppet = True

        check_call(
            [
                "ssh",
                performance_vm_fqdn,
                "sudo",
                "apt",
                "install",
                "fio",
                "--yes",
            ]
        )

    return performance_vm_fqdn


def execute_remote_test(
    host: str, site: Site, stack_level: StackLevel, base_outdir: str
) -> None:
    if stack_level in [
        StackLevel.rbd_from_osd,
        StackLevel.rbd_from_hypervisor,
    ]:
        extra_params = ["--pool", f"{site.value}-compute"]

    elif stack_level == StackLevel.vm_disk:
        extra_params = ["--file-path", "./performance_test.tmp"]

    elif stack_level == StackLevel.osd_disk:
        logging.warn("Not implemented yet")
        return

    check_call(
        [
            "./execute_remote_test.sh",
            "--stack-level",
            stack_level.name,
            "--remote-host",
            host,
            "--outdir",
            base_outdir,
            "--",
            *extra_params,
        ]
    )


STACK_TO_HOST = {
    StackLevel.rbd_from_osd: partial(
        get_random_netbox_host,
        hosts_query="cloudcephosd",
    ),
    StackLevel.rbd_from_hypervisor: partial(
        get_random_netbox_host,
        hosts_query="cloudvirt",
    ),
    StackLevel.vm_disk: get_performance_vm,
}


STACK_LEVEL_CONFIG_PER_SITE = {
    Site.codfw: {
        StackLevel.rbd_from_osd: {
            "extra_execute_params": ["--pool", "eqiad1-compute"],
        },
        StackLevel.rbd_from_hypervisor: {
            "extra_execute_params": ["--pool", "eqiad1-compute"],
        },
    }
}


@click.command()
@click.option(
    "-s",
    "--site-name",
    required=True,
    type=click.Choice([site.name for site in Site]),
)
@click.option(
    "-l",
    "--stack-level",
    multiple=True,
    default=[stack_level.name for stack_level in StackLevel],
    type=click.Choice([stack_level.name for stack_level in StackLevel]),
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
)
@click.option(
    "-o",
    "--outdir",
    required=False,
    default=(
        "results/full_stack/"
        + datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    ),
)
def cli(
    site_name: str, stack_level: List[str], outdir: str, verbose: bool
) -> None:
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    logging.debug(
        f"Running with site_name={site_name}, stack_level={stack_level}, "
        f"outdir={outdir}, verbose={verbose}"
    )
    stack_levels = [
        StackLevel[stack_level_name] for stack_level_name in stack_level
    ]
    site = Site[site_name]
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    for stack_level in STACK_TO_HOST.keys():
        if stack_level not in stack_levels:
            logging.debug(
                f"Skipping stack level {stack_level} as only {stack_levels} "
                "were requested."
            )
            continue

        host = STACK_TO_HOST[stack_level](site=site)
        logging.info(f"Running {stack_level.name} tests on host {host}.")
        execute_remote_test(
            host=host,
            site=site,
            stack_level=stack_level,
            base_outdir=outdir,
        )


if __name__ == "__main__":
    cli()
