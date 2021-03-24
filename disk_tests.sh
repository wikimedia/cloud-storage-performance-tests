#!/bin/bash -e
IOENGINE="libaio"
NUM_PASSES=3
OUTDIR="$PWD/${IOENGINE}_tests_results"


FIO_CONFS=(
    "4M:16:write"
    "4k:1:randwrite"
    "4k:128:randwrite"
    "4M:16:read"
    "4k:1:randread"
    "4k:128:randread"
)


help() {
    cat <<EOH
    Usage: $0 --file /dev/sdc [options]

    This will run a series of performance tests and leave one file per test with the results.
    Current fio tests configs:
        ${FIO_CONFS[@]}

    This runs tests by using directly rbd from fio (using engine $IOENGINE).

    Options
        --outdir OUTDIR
            Put all the results in this directory. Will be created if it does not exist (default $OUTDIR).

        --num-passes NUM_PASSES
            Run this many passes for each test (default $NUM_PASSES).

        --file file_path
            Use the given file path is the path to a file (or a non-existing file) it will create one and write/read
            to/from that, if it's a device (ex. /dev/sdc) it will use the whole device.

        -h/--help
            Show this help.
EOH
}


test_config() {
    local bs="${1:?No bs passed}"
    local rw="${2:?No rw passed}"
    local io="${3:?No io passed}"
    local num_passes="${4:?No num_passes passed}"
    local file_path="${5:?No file_path passed}"

    command -v fio &>/dev/null || {
        echo "This test needs fio to be installed on the host, but was not found. Aborting."
        exit 1
    }

    for i in $(seq "$num_passes"); do
        outdir="ioengine_${IOENGINE}.bs_${bs}.iodepth_${io}.rw_${rw}/run_$i"
        mkdir -p "$outdir"
        cd "$outdir"
        echo "## Running config (bs=$bs || rw=$rw || io=$io) iteration $i, results in $PWD"
        # Note that for the latencies, the only one we are interested in is clat -> completed latency, as we are always
        # syncing
        # the log_avg_msec has to be smaller than the bucket size for the graphs
        fio \
            --output-format='json+' \
            --ioengine="$IOENGINE" \
            --direct=1 \
            --name=test \
            --bs="$bs" \
            --iodepth="$io" \
            --rw="$rw" \
            --runtime=60 \
            --size=10G \
            --filename="$file_path" \
            --log_avg_msec=50 \
            --per_job_logs=0 \
            --write_lat_log=data \
            --write_bw_log=data \
            --write_iops_log=data \
        2>&1 \
        | tee "run_stats.log"
        [[ -f "$file_path" ]] && rm "$file_path"
        gzip ./*
        cd -
    done
}


main () {
    local file_path
    local num_passes="$NUM_PASSES"
    local outdir="$OUTDIR"
    local conf

    # Call getopt to validate the provided input.
    options=$(getopt -o h --long help,file-path:,outdir:,stack-level:,num-passes: -- "$@") \
    || {
        echo "Incorrect options provided."
        help
        exit 1
    }
    eval set -- "$options"
    while true; do
        case "$1" in
        -h|--help)
            help
            exit 0
            ;;
        --file-path)
            file_path=$2
            shift 2
            ;;
        --num-passes)
            num_passes=$2
            shift 2
            ;;
        --outdir)
            outdir=$2
            shift 2
            ;;
        --)
            break
            ;;
        esac
    done
    if [[ "$file_path" == "" ]]; then
        echo "No file path passed (--file-path)."
        help
        exit 1
    fi
    if [[ "$num_passes" == "" ]]; then
        echo "No number of passes passed (--num-passes)."
        help
        exit 1
    fi

    mkdir -p "$outdir"
    cd "$outdir"

    for conf in "${FIO_CONFS[@]}"; do
        bs="${conf%%:*}"
        rw="${conf##*:}"
        io="${conf#*:}"
        io="${io%:*}"
        test_config "$bs" "$rw" "$io" "$num_passes" "$file_path"
    done
}


main "$@"
