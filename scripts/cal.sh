#!/bin/bash

# DEFAULTS
VERBOSE=0
CONFIG_FILE="config.cfg"

# Parse input arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --verbose|-v)
            VERBOSE=1
            shift
            ;;
        --config_file|-c)
            CONFIG_FILE="$2"
            shift 2
            ;;
        -*)
            echo "Unknown option: $1"
            exit 1
            ;;
        *)
            echo "Unknown positional argument: $1"
            exit 1
            ;;
    esac
done

# Ensure the config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: Configuration file '$CONFIG_FILE' not found."
    exit 1
fi

# Function for verbose output
log() {
    if [ $VERBOSE -eq 1 ]; then
        echo "$@"
    fi
}

# Read TDC IDs from the [setup] section of the config file
TDC_IDS=$(awk -F '=' '/tdc_ids/ {print $2}' "$CONFIG_FILE" | tr ' ' '\n')

if [ -z "$TDC_IDS" ]; then
    echo "Error: TDC IDs not found in the configuration file."
    exit 1
fi

# Read the output directory from the [calibration] section of the config file
OUT_DIR=$(awk -F '=' '/out_dir/ {print $2}' "$CONFIG_FILE" | tr -d ' ')

if [ -z "$OUT_DIR" ]; then
    echo "Error: Output directory not found in the configuration file."
    exit 1
fi

# Ensure the output directory exists
mkdir -p "$OUT_DIR"

log "TDC IDs: $(echo $TDC_IDS | tr '\n' ' ')"
log "Output directory: $OUT_DIR"

log "TDC off"
dog -b write 0xfe000002 133 0x00000000
dog -b write 0xfe000002 133 0x00000000
dog -b write 0xfe000002 133 0x00000000
log "reset TDC FIFO"
dog -b write 0xfe000002 133 0x00001000
dog -b write 0xfe000002 133 0x00000032
log "start calibration"
dog -b write 0xfe000002 133 0x0000003a
sleep 2
dog -b write 0xfe000002 133 0x00000032

# Get a raw calibration file for each TDC module
log "Get raw calibration files"
for tdc_id in $TDC_IDS; do
    dog -b --short read -f -l 512 "$tdc_id" 72 > "$OUT_DIR/rc_${tdc_id}"
done
