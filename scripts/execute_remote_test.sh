#!/bin/bash -ex
# The following has to be in sync with the StackLevel python enum
declare -A TESTS=(
    [rbd_from_osd]=rbd_tests.sh
    [rbd_from_hypervisor]=rbd_tests.sh
    [osd_disk]=disk_tests.sh
    [vm_disk]=disk_tests.sh
)


help() {
    cat <<EOH
    Usage: $0 [-h|--help] --stack-level STACK_LEVEL --outdir OUTDIR --remote-host REMOTE_HOST -- [option_for_script [...]]

    Runs the given test on the given host and stores the results under '$outdir/<stack_level>/<host>/'.


    Options:
        -h|--help  Show this help.

        --stack-level STACK_LEVEL
            Stack level to use, one of:
$(printf '                * %s\n' "${!TESTS[@]}" | sort | uniq)

        --outdir OUTDIR
            Base directory where to put the results.

        --remote-host REMOTE_HOST
            Host to run the tests on.

        option_for_script [...]
            Everything else will be passed as parameters for the script. See the script help for more, current scripts:
$(printf '                * %s\n' "${TESTS[@]}" | sort | uniq)
EOH
}


main() {
    set -o pipefail
    local stack_level \
        outdir \
        host
    local num_passes=3

    # Call getopt to validate the provided input.
    options=$(getopt -o h --long help,outdir:,stack-level:,remote-host:,num-passes: -- "$@") \
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
        --outdir)
            outdir=$2
            shift 2
            ;;
        --stack-level)
            stack_level=$2
            shift 2
            ;;
        --remote-host)
            remote_host=$2
            shift 2
            ;;
        --num-passes)
            num_passes=$2
            shift 2
            ;;
        --)
            shift
            break
            ;;
        *)
            echo "Unknown parameter '$1'"
            help
            exit 1
        esac
    done
    if [[ "$outdir" == "" ]]; then
        echo "No outdir passed (--outdir)."
        help
        exit 1
    fi
    if [[ "$stack_level" == "" ]]; then
        echo "No stack level passed (--stack-level)."
        help
        exit 1
    fi
    if [[ "$remote_host" == "" ]]; then
        echo "No remote host passed (--remote-host)."
        help
        exit 1
    fi

    local script_file="${TESTS[$stack_level]}"

    if [[ "$script_file" == "" ]]; then
        echo -e "Invalid test type $stack_level, expected one of:\n    ${!TESTS[@]}\n"
        help 1
    fi

    local stack_level_dir="$outdir/${stack_level}"
    mkdir -p "$stack_level_dir"

    local results_dir="${stack_level_dir}/${remote_host}"

    sudo_cmd="sudo"
    user=""
    if [[ "$stack_level" == "vm_disk" ]]; then
        # We can run the vm tests directly with root
        sudo_cmd=""
        user="root@"
    fi

    echo "Executing $stack_level tests ($script_file) on ${user}${remote_host}, and storing in $results_dir..."
    local full_script_path="$(dirname $(realpath $0))/$script_file"
    scp "$full_script_path" "${user}${remote_host}:."
    ssh "${user}${remote_host}" \
        $sudo_cmd chown -R "$USER" perf_test_results 2>/dev/null || :
    ssh "${user}${remote_host}" \
        rm -rf perf_test_results
    ssh "${user}${remote_host}" \
        $sudo_cmd ./"$script_file"  \
        --outdir perf_test_results \
        --num-passes "$num_passes" \
        "$@"
    ssh "${user}${remote_host}" \
        $sudo_cmd chown -R "$USER" perf_test_results
    scp -r "${user}${remote_host}:perf_test_results" "$results_dir"


    cat > "$results_dir/metadata.json" <<EOM
{
    "test_info": {
        "num_passes": "$num_passes",
        "stack_level": "$stack_level",
        "script": "$script_file",
        "host": "$remote_host"
    }
}
EOM


    echo "The results of running the $stack_level tests ($script_file) on $remote_host are in $results_dir directory:"
    command -v tree &>/dev/null && tree -d "$results_dir" || :
}


main "$@"
