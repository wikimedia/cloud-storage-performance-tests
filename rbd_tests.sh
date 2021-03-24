#!/bin/bash -ex
IOENGINE="rbd"
IMAGE_NAME="fio_test"
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
    Usage: $0 --pool POOL_NAME [options]

    This will run a series of performance tests and leave one file per test with the results.
    Current fio tests configs:
        ${FIO_CONFS[@]}

    This runs tests by using directly rbd from fio (using engine $IOENGINE).

    Options
        --outdir OUTDIR
            Put all the results in this directory. Will be created if it does not exist (default $OUTDIR).

        --pool POOL_NAME
            Use the given pool.

        --num-passes NUM_PASSES
            Run this many passes for each test (default $NUM_PASSES).

        --image-name IMAGE_NAME
            Use the given image name (default $IMAGE_NAME).

        -h/--help
            Show this help.
EOH
}


create_and_populate_image() {
    local image_name="${1:?No image_name passed}"
    local pool="${2:?No pool passed}"
    local client="${3:?No client passed}"

    rbd remove \
        --pool "$pool" \
        --name "$client" \
        "$image_name" || :
    rbd create \
        --pool "$pool" \
        --name "$client" \
        --image "$image_name" \
        --size 10240 \
        --thick-provision
}


test_config() {
    local bs="${1:?No bs passed}"
    local rw="${2:?No rw passed}"
    local io="${3:?No io passed}"
    local num_passes="${4:?No num_passes passed}"
    local image_name="${5:?No image_name passed}"
    local pool="${6:?No pool passed}"
    local client="${7:?No client passed}"

    for i in $(seq "$num_passes"); do
        outdir="ioengine_${IOENGINE}.bs_${bs}.iodepth_${io}.rw_${rw}/run_$i"
        mkdir -p "$outdir"
        cd "$outdir"
        echo "## Running config (bs=$bs || rw=$rw || io=$io) iteration $i, results in $PWD"
        # Note that for the latencies, the only one we are interested in is clat -> completed latency, as we are always
        # syncing
        # fio adds the 'client.' to the rbd client name already.
        fio \
            --output-format='json+' \
            --ioengine="$IOENGINE" \
            --direct=1 \
            --name=test \
            --bs="$bs" \
            --iodepth="$io" \
            --rw="$rw" \
            --pool="$pool" \
            --runtime=60 \
            --clientname="${client#client.}" \
            --rbdname="$image_name" \
            --log_avg_msec=50 \
            --per_job_logs=0 \
            --write_lat_log=data \
            --write_bw_log=data \
            --write_iops_log=data \
        2>&1 \
        | tee "run_stats.log"
        gzip ./*
        cd -
    done
}


main () {
    local image_name="$IMAGE_NAME"
    local num_passes="$NUM_PASSES"
    local outdir="$OUTDIR"
    local conf
    local pool
    local client

    set -o pipefail

    command -v fio &>/dev/null || {
        echo "This test needs fio to be installed on the host, but was not found. Aborting."
        exit 1
    }

    # Call getopt to validate the provided input.
    options=$(getopt -o h --long help,pool:,image-name:,outdir:,num-passes: -- "$@") \
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
        --pool)
            pool=$2
            shift 2
            ;;
        --image-name)
            image_name=$2
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
    if [[ "$pool" == "" ]]; then
        echo "No pool passed (--pool)."
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

    if [[ -e "/etc/ceph/ceph.client.admin.keyring" ]]; then
        client="client.admin"
    else
        client="client.$pool"
    fi

    create_and_populate_image "$image_name" "$pool" "$client"
    for conf in "${FIO_CONFS[@]}"; do
        bs="${conf%%:*}"
        rw="${conf##*:}"
        io="${conf#*:}"
        io="${io%:*}"
        test_config "$bs" "$rw" "$io" "$num_passes" "$image_name" "$pool" "$client"
    done
}


main "$@"
