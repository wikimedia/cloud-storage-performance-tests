# Ceph Performance tests
## Installation

If you are using virtual envs:

    # only python3 is supported
    python3 -m venv /path/to/your/new/venv
    source /path/to/your/new/venv/bin/activate
    pip install -r requirements.txt

In order to be able to retrieve a list of hosts from netbox directly, you will have to add a config file under
"~/.config/netbox/config.json" with the contents:

    {
        "netbox_url": "https://netbox.wikimedia.org/api",
        "api_token": "your-api-token"
    }

To create an API token, you can got to https://netbox.wikimedia.org/user/api-tokens/

## Testing in layers

The goal of these scripts is to be able to asses if a change in the stack (new kernel, new ceph version, etc.) has had
any effect in the performance of the cluster.
With that in mind, the idea is to get a snapshot of all the stack levels of the deployment before and after, and build a
comparison for each of them.

You can also compare different levels of the stack at the same moment, though that's out of scope currently, currently
only 2 result sets can be compared at a time.

The chosen stack levels are:

* **osd_disk**: directly accessing the devices (/dev/sdX), no ceph stack involved, only kernel and hardware
* **rbd_from_osd**: (librbd + librados) from the osd nodes, that ensures that the network is the "best"
* **rbd_from_hypervisor**: (librdb + librados) from the hypervisors, this is the same stack that libvirt is configured
    to use (excluding libvirt itself)
* **vm_disk**: from inside the VM, using the disk that libvirt maps to rbd (VM fs/kernel + libvirt + librbd + librados).

## Gathering data
### Executing a full stack test

There's a python script `run_on_env.py` that will randomly gather one host from each stack level, run the test and
gather the results under the same directory (under 'results/<SITE_NAME>/<DATETIME>').

The results will be ready to use to generate a full stack comparison report.

### Executing a test on a single machine and gathering results

There's a helper script, `execute_remote_test.sh` that will run the given stack layer tests on the given host and copy
locally the results (in the results directory).


## Generating reports
### Generating a report from two full stack results

Once you have at least two different result sets (the directories under ./results), you can generate a comparative
report by running the script `generate_reports.py`, that will build a self-contained html page with interactive graphs
and some stats highlighting the results that are "better".

Example:

    ./generate_reports.py \
        --verbose env-report \
            --outfile-prefix reports/full_stack/2021-03-18_vs_2021-03-19 \
            --before-data-dir results/codfw/full_stack/2021-03-18_18-11-16 \
            --after-data-dir results/codfw/full_stack/2021-03-19_15-41-05/ \
            --description "No changes in between, just two plain runs."



### Generating a report from two single results

If you want to just compare two runs for a single stack level, or even compare just two any host runns, you can run
`generate_reports.py generate-level-report` and it will use only those two host runs. For example:


    ./generate_reports.py \
        level-report \
            --outfile-prefix $(date +%Y-%m-%d)_vm_against_osd \
            -d results/full_stack/codfw/2021-03-19_15-41-05/vm_disk/ \
            -n VM \
            -D results/full_stack/codfw/2021-03-19_15-41-05/rbd_from_osd/ \
            -N OSD

That will open a new browser window for you to preview the report. If everything is ok, in order to commit and make it
available, you can gzip it:
```
gzip *vm_against_osd.html
```
and move it to the reports directory:
```
mv *vm_against_osd.html.gz reports/full_stack/
```

Now you can commit the report and the results and send a patch.

## Functional details
### vm_disk tests

For the VM disk tests, a dedicated VM has been chosen due to having a rate limit on a per-VM basis setup on Openstack,
that if we were to run on an existing VM would affect any other service running on it.
It also allows for more reproducible test due to the VM level isolation (though might still be affected by noisy
neighbours at the hypervisor, network and ceph cluster levels).

### What is iodepth?
Essentially is the size of the 'queued' io requests fio submits at any time, it's a maximal limit, that might be
shortened by the OS.

Usually lower io depth means that each operation is flushed from the queue faster, giving lower latencies, but lower
iops, while highel io depth gives the opposite result, rising latencies (as operations might be now batched) up higher
iops (as it's overall more efficient in number of overall total iops).

Related docs:
* https://www.spinics.net/lists/fio/msg07191.html
* https://fio.readthedocs.io/en/latest/fio_man.html#cmdoption-arg-iodepth
