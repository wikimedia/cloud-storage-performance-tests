#!/usr/bin/env python3
"""
Expected full directory structure for a full run:


└── <TIMESTAMP>
    └── <STACK_LEVEL>
        └── <HOSTNAME>  # only one hostname per stack level
            └── <CONFIGURATION>
                └── <RUN>
                    ├── data_bw.log.gz
                    ├── data_iops.log.gz
                    ├── data_lat.log.gz
                    └── run_stats.log.gz


For example:

└── 2021-03-19_15-41-05
    ├── rbd_from_hypervisor
    |   └── ...
    ├── ...
    └── vm_disk
        └── performance-test.testlabs.codfw1dev.wikimedia.cloud
            ├── ioengine_libaio.bs_4k.iodepth_128.rw_randread
            ├── ...
            └── ioengine_libaio.bs_4M.iodepth_16.rw_write
                ├── run_1
                ├── ...
                └── run_3
                    ├── data_bw.log.gz
                    ├── data_iops.log.gz
                    ├── data_lat.log.gz
                    └── run_stats.log.gz
"""
import datetime
import gzip
import json
import logging
import os
from copy import copy
from dataclasses import dataclass
from enum import Enum, auto
from math import sqrt
from pprint import pformat
from typing import Any, Callable, Iterator, List, Optional, Tuple

import click
import numpy as np
from bokeh.io import curdoc, output_file
from bokeh.layouts import column
from bokeh.models import Div, HoverTool, Panel, Plot, Tabs
from bokeh.plotting import Figure, figure, gridplot, show
from numpy.typing import ArrayLike

NO_SAMPLES = -1
NANO_TO_MILI = 1 / (1000 * 1000)
KILO_TO_MEGA = 1 / 1024
MEGA_TO_BYTE = 1024 * 1024
KILO_TO_BYTE = 1024
DEFAULT_BACKGROUND = (37, 37, 37)
DEFAULT_STYLE = {
    "color": "rgb(231, 231, 231)",
    "background": "rgb(37, 37, 37)",
}


class Stat(Enum):
    latency = auto()
    bandwidth = auto()
    iops = auto()


class AggregationType(Enum):
    max = auto()
    min = auto()
    mean = auto()


class ReadWriteType(Enum):
    read = auto()
    write = auto()
    randwrite = auto()
    randread = auto()


class IOEngine(Enum):
    rbd = auto()
    libaio = auto()


class StackLevel(Enum):
    # TODO: not supported yet
    # osd_disk = auto()
    rbd_from_osd = auto()
    rbd_from_hypervisor = auto()
    vm_disk = auto()


STACK_LEVEL_DESCS = {
    StackLevel.rbd_from_osd: (
        "RBD from OSD: This test ran against the full cluster (using librbd) "
        "from one of the OSD daemons."
    ),
    StackLevel.rbd_from_hypervisor: (
        "RBD from Hypervisor: This test ran against the full cluster (using "
        "librbd) from one of the hypervisors."
    ),
    StackLevel.vm_disk: (
        "VM Disk: This test ran against the full cluster (using libaio) from "
        "one of the VMs, that creates a local file to test against and uses "
        "the full stack, from VM kernel, libvirt, librbd, etc. The iops might "
        "be getting throttled in this test affecting the results."
    ),
}

COMMON_DESC = """<div>The details in the configuration mean:
<ul>
<li>
    <b>rw:</b> type of read/write pattern, linear writes and reads usually get
    better perfromance due to caching.
</li>
<li>
    <b>bs:</b> block size, we test two sizes, 4K (small) and 4M (big), the
    former will give a result similar to writting/reading small files, usually
    smaller latencies but also lower bandwidth, the big block size gives lower
    latencies but higher bandwidth.
</li>
<li>
    <b>ioengine</b>: This is the fio engine used for the tests, we use two
    different ones, rbd (that uses librbd), and libaio, that uses the linux
    native asyinchronous I/O.
</li>
<li>
    <b>iodepth</b>: This is the maximum size of the io operation queue that fio
    will try to keep, a higher number means that more io operations will be
    queued in parallel, and gives more iops but it renders lower latency (as
    it will have to wait more for the io operations to finish).
</li>
</ul>
</div>
<div>
Each graph shows two sets of colored lines, corresponidng to each comparison
side. Each set has three lines, the maximum of all the runs, the mean of all
the runs and the minimum for all the runs for that configuration and date.
"""


@dataclass
class RunConfig:
    rw: ReadWriteType
    bs: int
    ioengine: IOEngine
    iodepth: int

    @classmethod
    def from_file(cls, file_path: str) -> "RunConfig":
        if file_path.endswith(".gz"):
            open_fn = gzip.open
        else:
            open_fn = open

        config_dict = json.load(open_fn(file_path))
        rw = ReadWriteType[config_dict["jobs"][0]["job options"]["rw"]]
        raw_bs = config_dict["jobs"][0]["job options"]["bs"].lower()
        if "m" in raw_bs:
            bs = int(raw_bs[:-1]) * MEGA_TO_BYTE

        elif "k" in raw_bs:
            bs = int(raw_bs[:-1]) * KILO_TO_BYTE

        else:
            bs = int(raw_bs)

        ioengine = IOEngine[config_dict["global options"]["ioengine"]]
        iodepth = int(config_dict["jobs"][0]["job options"]["iodepth"])
        return cls(rw=rw, bs=bs, ioengine=ioengine, iodepth=iodepth)

    def __eq__(self, other) -> bool:
        """We want to ignore the engine so we can compare different engines."""
        return (
            self.bs == other.bs
            and self.rw == other.rw
            and self.iodepth == other.iodepth
        )

    def __str__(self) -> str:
        return (
            f"RunConfig(rw={self.rw.name}, bs={self.bs}, "
            f"ioengine={self.ioengine.name}, iodepth={self.iodepth})"
        )


@dataclass
class BaseStats:
    stat: Stat
    max: int
    min: int
    mean: float
    stddev: float
    # only set for latency
    ninety_percentile: int = 0


@dataclass
class RunStats:
    latency: BaseStats
    bandwidth: BaseStats
    iops: BaseStats

    @classmethod
    def from_file(cls, file_path: str) -> "RunStats":
        if file_path.endswith(".gz"):
            open_fn = gzip.open
        else:
            open_fn = open

        stats_dict = json.load(open_fn(file_path))
        job_dict = stats_dict["jobs"][0]
        if job_dict["job options"]["rw"] in ["read", "randread"]:
            stats_dict = job_dict["read"]
        else:
            stats_dict = job_dict["write"]

        latency = BaseStats(
            max=stats_dict["clat_ns"]["max"] * NANO_TO_MILI,
            min=stats_dict["clat_ns"]["min"] * NANO_TO_MILI,
            mean=stats_dict["clat_ns"]["mean"] * NANO_TO_MILI,
            stddev=stats_dict["clat_ns"]["stddev"] * NANO_TO_MILI,
            ninety_percentile=(
                stats_dict["clat_ns"]["percentile"]["90.000000"] * NANO_TO_MILI
            ),
            stat=Stat.latency,
        )
        bandwidth = BaseStats(
            max=stats_dict["bw_max"] * KILO_TO_MEGA,
            min=stats_dict["bw_min"] * KILO_TO_MEGA,
            mean=stats_dict["bw_mean"] * KILO_TO_MEGA,
            stddev=stats_dict["bw_dev"] * KILO_TO_MEGA,
            stat=Stat.bandwidth,
        )
        iops = BaseStats(
            max=stats_dict["iops_max"],
            min=stats_dict["iops_min"],
            mean=stats_dict["iops_mean"],
            stddev=stats_dict["iops_stddev"],
            stat=Stat.iops,
        )
        return cls(
            latency=latency,
            bandwidth=bandwidth,
            iops=iops,
        )


@dataclass
class StatReport:
    data: ArrayLike
    stat: Stat

    @classmethod
    def from_file(cls, file_path: str) -> "StatReport":
        if "data_lat" in file_path:
            stat = Stat.latency
        elif "data_bw" in file_path:
            stat = Stat.bandwidth
        elif "data_iops" in file_path:
            stat = Stat.iops
        else:
            raise Exception(
                f"Unable to guess report type for file {file_path}."
            )

        data = np.fromiter(
            iter_data(file_path=file_path, stat=stat),
            dtype="i,f",
        )
        return cls(data=data, stat=stat)

    def __eq__(self, other) -> bool:
        return self.stat == other.stat

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        return f"StatReport(stat={self.stat}, len(data)={len(self.data)})"


@dataclass
class AggregatedRunStatReport:
    data: ArrayLike
    stat: Stat
    aggregation_type: AggregationType
    num_merged_reports: int = 1

    @classmethod
    def from_stat_report(
        cls,
        stat_report: StatReport,
        aggregation_type: AggregationType,
    ) -> "AggregatedRunStatReport":
        return cls(
            data=stat_report.data.copy(),
            stat=stat_report.stat,
            aggregation_type=aggregation_type,
        )

    def __eq__(self, other) -> bool:
        return self.stat == other.stat

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        return (
            f"StatReport(stat={self.stat}, len(data)={len(self.data)}, "
            f"num_merged_reports={self.num_merged_reports})"
        )

    def add_stat_report(self, stat_report: StatReport) -> None:
        if stat_report.stat != self.stat:
            raise Exception(
                f"Unable to merge a report of statistic {stat_report.stat} "
                f"into an aggregated report for statistic {self.stat}."
            )

        self.num_merged_reports += 1
        if self.aggregation_type == AggregationType.max:
            sanitized_self_data = self.data["f1"].copy()
            sanitized_report_data = stat_report.data["f1"].copy()
            # fills up each other with the other's data if it's there
            sanitized_self_data[
                sanitized_self_data == NO_SAMPLES
            ] = sanitized_report_data[sanitized_self_data == NO_SAMPLES]
            sanitized_report_data[
                sanitized_report_data == NO_SAMPLES
            ] = sanitized_self_data[sanitized_report_data == NO_SAMPLES]
            self.data["f1"] = np.maximum(
                sanitized_self_data, sanitized_report_data
            )

        elif self.aggregation_type == AggregationType.min:
            sanitized_self_data = self.data["f1"].copy()
            sanitized_report_data = stat_report.data["f1"].copy()
            # fills up each other with the other's data if it's there
            sanitized_self_data[
                sanitized_self_data == NO_SAMPLES
            ] = sanitized_report_data[sanitized_self_data == NO_SAMPLES]
            sanitized_report_data[
                sanitized_report_data == NO_SAMPLES
            ] = sanitized_self_data[sanitized_report_data == NO_SAMPLES]
            self.data["f1"] = np.minimum(
                sanitized_self_data, sanitized_report_data
            )

        elif self.aggregation_type == AggregationType.mean:
            sanitized_self_data = self.data["f1"].copy()
            sanitized_report_data = stat_report.data["f1"].copy()
            # fills up each other with the other's data if it's there
            sanitized_self_data[
                sanitized_self_data == NO_SAMPLES
            ] = sanitized_report_data[sanitized_self_data == NO_SAMPLES]
            sanitized_report_data[
                sanitized_report_data == NO_SAMPLES
            ] = sanitized_self_data[sanitized_report_data == NO_SAMPLES]

            self.data["f1"] = (
                sanitized_self_data
                - sanitized_self_data / self.num_merged_reports
                + sanitized_report_data / self.num_merged_reports
            )


@dataclass
class RunReport:
    latency_report: Optional[StatReport]
    bandwidth_report: Optional[StatReport]
    iops_report: Optional[StatReport]
    run_stats: RunStats
    run_config: RunConfig

    @classmethod
    def from_dir(cls, dir_path: str, stats: List[Stat]) -> "RunReport":
        """The directory has to have the structure:

                └── run_1
                    ├── data_bw.log.gz
                    ├── data_iops.log.gz
                    ├── data_lat.log.gz
                    └── run_stats.log.gz

        The path has to have inside 4 mandatory files, the bandwidth data
        (data_bw.log.gz), the iops data (data_iops.log), the latency data
        (data_lat.log.gz) and the general info/stats (run_stats.log.gz) as
        outputted by:
            fio \
                --format=+json \
                --write_lat_log=data \
                --write_bw_log=data \
                --write_iops_log=data
        """
        latency_report = bandwidth_report = iops_report = None

        if Stat.latency in stats:
            latency_report = StatReport.from_file(
                os.path.join(dir_path, "data_lat.log.gz")
            )

        if Stat.bandwidth in stats:
            bandwidth_report = StatReport.from_file(
                os.path.join(dir_path, "data_bw.log.gz")
            )

        if Stat.iops in stats:
            iops_report = StatReport.from_file(
                os.path.join(dir_path, "data_iops.log.gz")
            )

        run_config = RunConfig.from_file(
            os.path.join(dir_path, "run_stats.log.gz")
        )
        run_stats = RunStats.from_file(
            os.path.join(dir_path, "run_stats.log.gz")
        )
        return cls(
            latency_report=latency_report,
            bandwidth_report=bandwidth_report,
            iops_report=iops_report,
            run_config=run_config,
            run_stats=run_stats,
        )

    def __eq__(self, other: "RunReport") -> bool:
        def _both_are_none_or_not_none(
            one: Optional[Any], other: Optional[Any]
        ) -> bool:
            return (one is None and other is None) or (
                one is not None and other is not None
            )

        return (
            self.run_config == other.run_config
            and _both_are_none_or_not_none(
                self.bandwidth_report, other.bandwidth_report
            )
            and _both_are_none_or_not_none(self.iops_report, other.iops_report)
            and _both_are_none_or_not_none(
                self.latency_report, other.latency_report
            )
        )


@dataclass
class AggregatedRunReport:
    max_latency_report: Optional[AggregatedRunStatReport] = None
    min_latency_report: Optional[AggregatedRunStatReport] = None
    mean_latency_report: Optional[AggregatedRunStatReport] = None
    max_bandwidth_report: Optional[AggregatedRunStatReport] = None
    min_bandwidth_report: Optional[AggregatedRunStatReport] = None
    mean_bandwidth_report: Optional[AggregatedRunStatReport] = None
    max_iops_report: Optional[AggregatedRunStatReport] = None
    min_iops_report: Optional[AggregatedRunStatReport] = None
    mean_iops_report: Optional[AggregatedRunStatReport] = None
    aggregated_stats: Optional[RunStats] = None
    num_merged_reports: int = 0

    def _add_report(
        self, aggregation_type: AggregationType, report: StatReport
    ) -> None:
        report_name = f"{aggregation_type.name}_{report.stat.name}_report"
        if not getattr(self, report_name):
            setattr(
                self,
                report_name,
                AggregatedRunStatReport.from_stat_report(
                    stat_report=report, aggregation_type=aggregation_type
                ),
            )
        else:
            getattr(self, report_name).add_stat_report(report)

    def _add_aggregation_reports(self, report: Optional[StatReport]) -> None:
        if not report:
            return

        for aggregation_type in AggregationType:
            self._add_report(aggregation_type=aggregation_type, report=report)

    def _add_aggregated_stats(self, run_stats: RunStats) -> None:
        if self.aggregated_stats is None:
            self.aggregated_stats = copy(run_stats)
            return

        for stat in Stat:
            self._add_aggregated_stat_stats(
                stats=getattr(run_stats, stat.name)
            )

    def _add_aggregated_stat_stats(self, stats: BaseStats) -> None:
        my_stat = getattr(self.aggregated_stats, stats.stat.name)

        my_stat.max = max(my_stat.max, stats.max)
        my_stat.min = min(my_stat.min, stats.min)
        # This avoids overflowing to some extent. Things to note:
        # * we are giving the same weight to each run
        # * this is the mean of the means of the runs
        # * num_runs includes the current run
        #
        #   mean = (cur_mean * (num_runs - 1) + new_run_mean) / num_runs
        #   => mean = (
        #          cur_mean * num_runs - cur_mean + new_run_mean
        #      ) / num_runs
        #   => mean = cur_mean - cur_mean / num_runs + new_run_mean / num_runs
        #
        my_stat.mean = (
            my_stat.mean
            - my_stat.mean / self.num_merged_reports
            + stats.mean / self.num_merged_reports
        )

        # For the stddev, the way of aggregating is by summing the variance
        # and then doing the square root to get the stddev again.
        #    stddev = sqrt(stddev1^2 + stddev2^2)
        my_stat.stddev = sqrt(my_stat.stddev ** 2 + stats.stddev ** 2)

    def add_run_report(self, run_report: RunReport) -> None:
        # if moving this increment after adding aggregated stats, change the
        # mean calculation
        self.num_merged_reports += 1
        self._add_aggregation_reports(run_report.bandwidth_report)
        self._add_aggregation_reports(run_report.iops_report)
        self._add_aggregation_reports(run_report.latency_report)
        self._add_aggregated_stats(run_report.run_stats)


@dataclass
class ConfigReport:
    runs: List[RunReport]
    config: RunConfig
    aggregated_run: AggregatedRunReport

    @classmethod
    def from_dir(cls, dir_path: str, stats: List[Stat]) -> "ConfigReport":
        """The directory has to have the structure:

            └── config_dir
                ├── run_1
                |   ...
                └── run_2
                    ...

        Where each of the subdirs is a different run for that configuration
        (see RunReport.from_dir).
        """
        aggregated_run_report = AggregatedRunReport()
        runs = []
        for run_dir in os.listdir(dir_path):
            if not os.path.isdir(os.path.join(dir_path, run_dir)):
                continue

            run = RunReport.from_dir(
                dir_path=os.path.join(dir_path, run_dir), stats=stats
            )
            if runs:
                if run.run_config != runs[0].run_config:
                    raise Exception(
                        "Got some reports with different configs under "
                        f"{dir_path}:\n{run}\n{runs[0]}"
                    )

            runs.append(run)
            aggregated_run_report.add_run_report(run_report=run)

        if not runs:
            raise Exception("Unable to load any runs.")

        runs.sort(key=str)
        return cls(
            runs=runs,
            aggregated_run=aggregated_run_report,
            config=runs[0].run_config,
        )

    def __eq__(self, other) -> bool:
        return self.config == other.config


@dataclass
class StackLevelReport:
    config_reports: List[ConfigReport]
    stack_level: StackLevel
    hostname: str

    @classmethod
    def from_dir(
        cls, stack_level: StackLevel, dir_path: str, stats=List[Stat]
    ) -> "StackLevelReport":
        """The directory has to have the structure:

            └── stack_level_dir
                └── hostname
                    ├── config1_dir
                    |   ...
                    └── config2_dir
                        ...

        Where each of the subdirs is a different run for that configuration
        (see RunReport.from_dir).

        TODO: support more than one hostname (probably split the report).
        """
        subdirs = [
            subdir
            for subdir in os.listdir(dir_path)
            if os.path.isdir(os.path.join(dir_path, subdir))
        ]

        if len(subdirs) != 1:
            raise Exception(
                f"Under the directory {dir_path} should be one and only one "
                "subdirectory, named after the host the tests ran on. Got "
                f"{subdirs}."
            )
        hostname = subdirs[0]
        configs_dir = os.path.join(dir_path, hostname)
        config_reports = list(
            sorted(
                (
                    ConfigReport.from_dir(
                        dir_path=os.path.join(configs_dir, config_dir),
                        stats=stats,
                    )
                    for config_dir in os.listdir(configs_dir)
                    if os.path.isdir(os.path.join(configs_dir, config_dir))
                ),
                key=lambda cr: str(cr.config),
            )
        )

        return cls(
            hostname=hostname,
            config_reports=config_reports,
            stack_level=stack_level,
        )

    def __eq__(self, other: "StackLevelReport") -> bool:
        return self.config_reports == other.config_reports


@dataclass
class SnapshotReport:
    stack_level_reports: List[StackLevelReport]
    timestamp: datetime.datetime

    @classmethod
    def from_dir(
        cls, dir_path: str, stats: List[Stat], stack_levels: List[StackLevel]
    ) -> "SnapshotReport":
        """The directory has to have the structure:

            └── TIMESTAMP
                ├── stack_level1
                |   ...
                └── stack_level2
                    ...

        For example:

            └── 2021-03-19_17-32-41
                ├── rbd_from_osd
                |   ...
                ├── rbd_from_hypervisor
                |   ...
                └── vm_disk
                    ...

        Where each of the subdirs is a different stack level for that date.
        """
        logging.debug(
            f"Generating SnapshotReport form dir {dir_path} with "
            f"stack_levels {stack_levels} and stats {stats}"
        )
        stack_level_reports = [
            StackLevelReport.from_dir(
                dir_path=os.path.join(dir_path, stack_dir),
                stats=stats,
                stack_level=StackLevel[stack_dir],
            )
            for stack_dir in os.listdir(dir_path)
            if os.path.isdir(os.path.join(dir_path, stack_dir))
            and stack_dir in [stack_level.name for stack_level in stack_levels]
        ]
        logging.debug(
            f"Got {len(stack_level_reports)} stack level reports, for the "
            "stack levels "
            + str(
                [
                    level_report.stack_level
                    for level_report in stack_level_reports
                ]
            )
        )
        return cls(
            stack_level_reports=stack_level_reports,
            timestamp=datetime.datetime.strptime(
                os.path.basename(dir_path), "%Y-%m-%d_%H-%M-%S"
            ),
        )

    def __eq__(self, other: "SnapshotReport") -> bool:
        return sorted(self.stack_level_reports) == sorted(
            other.stack_level_reports
        )


def iter_data(file_path: str, stat: Stat) -> Iterator[Tuple[int, float]]:
    """
    From fio man page:
    LOG FILE FORMATS
        Fio supports a variety of log file formats, for logging latencies,
        bandwidth, and IOPS. The logs share a common format, which looks like
        this:

                time (msec), value, data direction, block size (bytes), \
                offset (bytes), command priority

        `Time' for the log entry is always in milliseconds. The `value' logged
        depends on the type of log, it will be one of the following:

                Latency log
                        Value is latency in nsecs

                Bandwidth log
                        Value is in KiB/sec

                IOPS log
                        Value is IOPS

        `Data direction' is one of the following:

                0      I/O is a READ

                1      I/O is a WRITE

                2      I/O is a TRIM

        The entry's `block size' is always in bytes. The `offset' is the
        position in bytes from the start of the file for that particular I/O.
        The logging of the offset can be toggled with log_offset.

        `Command priority` is 0 for normal priority and 1 for high priority.
        This is controlled by the ioengine specific cmdprio_percentage.

        Fio  defaults  to  logging every individual I/O but when windowed
        logging is set through log_avg_msec, either the average (by default) or
        the maximum (log_max_value is set) `value' seen over the specified
        period of time is recorded. Each `data direction' seen within the
        window period will aggregate its values in a separate row. Further,
        when using windowed logging the `block size' and `offset' entries will
        always contain 0.
    """
    # 60 seconds test run is up to 60.000 samples (1/ms), +1 xd
    if file_path.endswith(".gz"):
        open_fn = gzip.open
    else:
        open_fn = open

    buckets_per_sec = 10
    # buckets per second, for 60 sec test duration, plus some (tests might
    # end right after 60s)
    max_bucket = 60 * buckets_per_sec + 10
    cur_bucket = 0
    cur_bucket_value = 0
    num_values_in_bucket = 0
    for line in open_fn(file_path, "rt").readlines():
        # latency format is:
        # time/tick, latency_nanoseconds, read(0)/write(1), size
        time_str_ms, value, _ = [elem.strip() for elem in line.split(",", 2)]
        # we get ms, we want deciseconds (10 buckets/second)
        time_bucket = int(time_str_ms) // (1000 / buckets_per_sec)

        while time_bucket > cur_bucket and cur_bucket < max_bucket:
            yield (cur_bucket, cur_bucket_value)
            # flag buckets without any samples so we can filter later
            cur_bucket_value = NO_SAMPLES
            num_values_in_bucket = 0
            cur_bucket += 1

        if cur_bucket >= max_bucket:
            break

        # mean of the values inside the bucket
        num_values_in_bucket += 1
        if stat == Stat.iops:
            new_value = int(value)
        elif stat == Stat.latency:
            new_value = int(value) * NANO_TO_MILI
        elif stat == Stat.bandwidth:
            new_value = int(value) * KILO_TO_MEGA

        cur_bucket_value = (
            cur_bucket_value * (num_values_in_bucket - 1) + new_value
        ) / num_values_in_bucket

    logging.debug(
        f"Got {cur_bucket} (max_bucket={max_bucket}) buckets from {file_path}"
    )
    yield (cur_bucket, cur_bucket_value)

    # pad with 0s, so we have arrays of the same shape/dimension to operate
    # with
    while cur_bucket < max_bucket:
        cur_bucket += 1
        yield cur_bucket, NO_SAMPLES


def get_new_figure(stat: Stat, num_runs: int) -> Figure:
    if stat == Stat.latency:
        y_label = "latency(ms)"
    elif stat == Stat.bandwidth:
        y_label = "bandwidth(MiB/s)"
    elif stat == Stat.iops:
        y_label = "iops"

    return figure(
        title=f"{stat.name} - max/mean/min of #{num_runs} runs",
        x_axis_label="time(s)",
        y_axis_label=y_label,
    )


def add_stat_aggregated_run_lines(
    figure: Figure,
    base_run: AggregatedRunReport,
    base_name: str,
    target_run: AggregatedRunReport,
    target_name: str,
    stat: Stat,
) -> None:
    for aggregation_type in AggregationType:
        base_stat_report = getattr(
            base_run, f"{aggregation_type.name}_{stat.name}_report"
        )
        target_stat_report = getattr(
            target_run, f"{aggregation_type.name}_{stat.name}_report"
        )
        if aggregation_type == AggregationType.mean:
            dash_pattern = "solid"
        else:
            dash_pattern = "dotted"

        add_stat_aggregated_run_line(
            figure=figure,
            run_stat_report=base_stat_report,
            color="blue",
            dash_pattern=dash_pattern,
        )
        add_stat_aggregated_run_line(
            figure=figure,
            run_stat_report=target_stat_report,
            color="red",
            dash_pattern=dash_pattern,
        )


def add_stat_aggregated_run_line(
    figure: Figure,
    run_stat_report: AggregatedRunStatReport,
    color: str,
    dash_pattern: str,
) -> None:
    figure.line(
        x=(
            run_stat_report.data["f0"][
                run_stat_report.data["f1"] != NO_SAMPLES
            ]
            / 10
        ),
        y=run_stat_report.data["f1"][run_stat_report.data["f1"] != NO_SAMPLES],
        line_color=color,
        line_width=2,
        line_dash=dash_pattern,
    )


def add_hover_tooltip(figure_obj: Figure, stat: Stat) -> None:
    return
    if stat == Stat.latency:
        y_label = "latency"
    elif stat == Stat.bandwidth:
        y_label = "bandwidth"
    elif stat == Stat.iops:
        y_label = "iops"

    figure_obj.add_tools(
        HoverTool(
            tooltips=[
                # ("time", "@x"),
                (y_label, "@y"),
            ],
            mode="vline",
        )
    )


def _get_table_row(
    stat_name: str,
    units: str,
    base_is_better_fn: Callable[..., bool],
    base_value: Any,
    target_value: Any,
) -> str:
    if base_is_better_fn(base_value, target_value):
        base_color = "green"
        target_color = "yellow"
    else:
        base_color = "yellow"
        target_color = "green"

    return f"""
        <tr>
            <th>{stat_name}</th>
            <th style="color:{base_color};">{base_value:.2f} {units}</th>
            <th style="color:{target_color};">{target_value:.2f} {units}</th>
        </tr>
    """


def _get_stat_table(
    base_name: str,
    base_stats: BaseStats,
    target_name: str,
    target_stats: BaseStats,
    base_is_better_fn: Callable[..., bool],
    config: RunConfig,
    with_ninety_percentile: bool = False,
) -> None:
    if base_stats.stat == Stat.iops:
        unit = "iops"
    elif base_stats.stat == Stat.bandwidth:
        unit = "Mb/s"
    elif base_stats.stat == Stat.latency:
        unit = "ms"

    ninety_percent_row = ""
    if with_ninety_percentile:
        ninety_percent_row = _get_table_row(
            stat_name="ninety_percentile",
            units=unit,
            base_value=base_stats.ninety_percentile,
            target_value=target_stats.ninety_percentile,
            base_is_better_fn=base_is_better_fn,
        )

    return Div(
        text=f"""
        {base_stats.stat.name} - {config}
        <table width="100%">
            <tr>
                <th></th>
                <th style="color:blue;">{base_name}</th>
                <th style="color:red;">{target_name}</th>
            </tr>
            {_get_table_row(
                stat_name="mean",
                units=unit,
                base_is_better_fn=base_is_better_fn,
                base_value=base_stats.mean,
                target_value=target_stats.mean,
            )}
            {_get_table_row(
                stat_name="max",
                units=unit,
                base_is_better_fn=base_is_better_fn,
                base_value=base_stats.max,
                target_value=target_stats.max,
            )}
            {_get_table_row(
                stat_name="min",
                units=unit,
                base_is_better_fn=base_is_better_fn,
                base_value=base_stats.min,
                target_value=target_stats.min,
            )}
            {_get_table_row(
                stat_name="stddev",
                units="",
                base_is_better_fn=base_is_better_fn,
                base_value=base_stats.stddev,
                target_value=target_stats.stddev,
            )}
            {ninety_percent_row}
        </table>
        <div style="color:grey;">*As given by fio</div>
        """,
        style=DEFAULT_STYLE,
    )


def get_run_comparative_report_tab(
    base_run: AggregatedRunReport,
    base_name: str,
    target_run: AggregatedRunReport,
    target_name: str,
    stats: List[Stat],
    config: RunConfig,
) -> Panel:
    config_figures = []
    for stat in stats:
        # TODO: add a min + max + mean lines from each side
        new_figure = get_new_figure(
            stat=stat, num_runs=base_run.num_merged_reports
        )
        add_stat_aggregated_run_lines(
            figure=new_figure,
            base_run=base_run,
            base_name=base_name,
            target_run=target_run,
            target_name=target_name,
            stat=stat,
        )
        add_hover_tooltip(figure_obj=new_figure, stat=stat)

        config_figures.append(new_figure)
        if stat.name == "latency":

            def _base_is_better(base_value, target_value) -> bool:
                return base_value < target_value

        else:

            def _base_is_better(base_value, target_value) -> bool:
                return base_value > target_value

        config_figures.append(
            _get_stat_table(
                base_name=base_name,
                base_stats=getattr(base_run.aggregated_stats, stat.name),
                target_name=target_name,
                target_stats=getattr(target_run.aggregated_stats, stat.name),
                with_ninety_percentile=(stat.name == "latency"),
                base_is_better_fn=_base_is_better,
                config=config,
            )
        )

    return Panel(
        child=gridplot(children=config_figures, ncols=2, merge_tools=False),
        title=f"{config}",
    )


def compare_level_reports(
    stats: List[Stat],
    base_report: StackLevelReport,
    base_report_name: str,
    target_report: StackLevelReport,
    target_report_name: str,
) -> Plot:
    if base_report != target_report:
        raise Exception(
            f"There's different reports in the taget directory "
            f"than in the base directory: \n"
            f"Base reports: {pformat(base_report)}\n"
            f"Target reports:{pformat(target_report)}"
        )

    tabs = []
    for base_config_report, target_config_report in zip(
        base_report.config_reports, target_report.config_reports
    ):
        tabs.append(
            get_run_comparative_report_tab(
                base_run=base_config_report.aggregated_run,
                base_name=base_report_name,
                target_run=target_config_report.aggregated_run,
                target_name=target_report_name,
                config=base_config_report.config,
                stats=stats,
            )
        )

    return Tabs(
        tabs=tabs,
        tabs_location="right",
        background=DEFAULT_BACKGROUND,
    )


def compare_snapshot_reports(
    before: SnapshotReport, after: SnapshotReport, stats: List[Stat]
) -> Plot:
    level_report_figures = [
        Panel(
            title=f"{before_satck_report.stack_level.name}",
            child=column(
                Div(
                    text=(
                        STACK_LEVEL_DESCS[before_satck_report.stack_level]
                        + COMMON_DESC
                    ),
                    style=DEFAULT_STYLE,
                ),
                compare_level_reports(
                    stats=stats,
                    base_report=before_satck_report,
                    base_report_name=(
                        f"{before_satck_report.stack_level.name} - before"
                    ),
                    target_report=after_stack_report,
                    target_report_name=(
                        f"{after_stack_report.stack_level.name} - after"
                    ),
                ),
            ),
        )
        for (before_satck_report, after_stack_report) in zip(
            before.stack_level_reports, after.stack_level_reports
        )
    ]

    logging.debug(
        f"Generating snapshot report Tab panel for {len(level_report_figures)}"
        " level reports."
    )
    return Tabs(
        tabs=level_report_figures,
        tabs_location="above",
        background=DEFAULT_BACKGROUND,
    )


@click.option("-v", "--verbose", is_flag=True)
@click.group()
def cli(verbose: bool):
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)


@cli.command(
    help=(
        "Generate a report comparing only two sets of configs, usually from "
        "the same stack level."
    )
)
@click.option("-p", "--outfile-prefix", required=True)
@click.option("-d", "--base-directory", required=True)
@click.option("-n", "--base-report-name", required=True)
@click.option("-D", "--target-directory", required=True)
@click.option("-N", "--target-report-name", required=True)
@click.option(
    "--stack-level",
    "stack_level_name",
    help="Stack level for which the report is being generated.",
    required=False,
    default=StackLevel.rbd_from_osd.name,
    type=click.Choice([stack_level.name for stack_level in StackLevel]),
)
@click.option(
    "--stat",
    "stat_names",
    help=(
        "Only generate a report for this statistic. Will generate all by "
        "default."
    ),
    multiple=True,
    default=[stat.name for stat in Stat],
    type=click.Choice([stat.name for stat in Stat]),
)
def level_report(
    outfile_prefix: str,
    base_directory: str,
    base_report_name: str,
    target_directory: str,
    target_report_name: str,
    stack_level_name: str,
    stat_names: List[str],
):
    stats = [Stat[stat_name] for stat_name in stat_names]
    stack_level = StackLevel[stack_level_name]
    output_file_name = f"{outfile_prefix}.html"
    click.echo(f"Building comparative report at {output_file_name}...")
    output_file(output_file_name, mode="inline")
    curdoc().theme = "dark_minimal"
    base_report = StackLevelReport.from_dir(
        stack_level=stack_level, dir_path=base_directory, stats=stats
    )
    target_report = StackLevelReport.from_dir(
        stack_level=stack_level, dir_path=target_directory, stats=stats
    )
    report_plot = compare_level_reports(
        stats=stats,
        base_report=base_report,
        base_report_name=base_report_name,
        target_report=target_report,
        target_report_name=target_report_name,
    )

    show(report_plot)


@cli.command(
    help="This will generate a full report for each level of the stack"
)
@click.option("-p", "--outfile-prefix", required=True)
@click.option(
    "-b",
    "--before-data-dir",
    required=True,
    help="Directory with the results per-layer to use.",
)
@click.option(
    "-a",
    "--after-data-dir",
    required=True,
    help="Directory with the results per-layer to use.",
)
@click.option(
    "--stack-level",
    "stack_level_names",
    help="Stack level for which the report is being generated.",
    multiple=True,
    default=[stack_level.name for stack_level in StackLevel],
    type=click.Choice([stack_level.name for stack_level in StackLevel]),
)
@click.option(
    "--stat",
    "stat_names",
    help=(
        "Only generate a report for this statistic. Will generate all by "
        "default."
    ),
    multiple=True,
    default=[stat.name for stat in Stat],
    type=click.Choice([stat.name for stat in Stat]),
)
@click.option(
    "--description",
    help=("Short text describing the report itself, to give some context."),
    default="",
)
def env_report(
    outfile_prefix: str,
    before_data_dir: str,
    after_data_dir: str,
    stack_level_names: List[str],
    stat_names: List[str],
    description: str,
):
    stats = [Stat[stat_name] for stat_name in stat_names]
    stack_levels = [StackLevel[level_name] for level_name in stack_level_names]

    output_file_name = f"{outfile_prefix}.html"
    click.echo(f"Building comparative report at {output_file_name}...")
    output_file(output_file_name, mode="inline")
    curdoc().theme = "dark_minimal"
    if before_data_dir.endswith("/"):
        before_data_dir = before_data_dir[:-1]
    if after_data_dir.endswith("/"):
        after_data_dir = after_data_dir[:-1]

    before_report = SnapshotReport.from_dir(
        dir_path=before_data_dir,
        stats=stats,
        stack_levels=stack_levels,
    )
    after_report = SnapshotReport.from_dir(
        dir_path=after_data_dir,
        stats=stats,
        stack_levels=stack_levels,
    )
    full_report = compare_snapshot_reports(
        before=before_report, after=after_report, stats=stats
    )
    side_text = f"""<h1>
            Full Stack comparison of {before_data_dir} vs {after_data_dir}
        </h1>
        <div>{description}</div>
        """
    desc_div = Div(
        text=side_text,
        style=DEFAULT_STYLE,
    )
    show(column(desc_div, full_report))


if __name__ == "__main__":
    cli()
