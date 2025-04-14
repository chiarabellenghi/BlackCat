#!/bin/bash

# DEFAULTS
VERBOSE=0

# Parse input arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --verbose|-v)
            VERBOSE=1
            shift
            ;;
        --ext_device|-e)
            EXT_DEVICE="$2"
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

# Function for verbose output
log() {
    if [ $VERBOSE -eq 1 ]; then
        echo "$@"
    fi
}

# Check if EXT_DEVICE is set
if [ -z "$EXT_DEVICE" ]; then
    echo "Error: --ext_device|-e argument is required."
    exit 1
fi

# Check if EXT_DEVICE is a valid file or device
if [ ! -e "$EXT_DEVICE" ]; then
    echo "Error: EXT_DEVICE '$EXT_DEVICE' does not exist."
    exit 1
fi

# Log the EXT_DEVICE value if verbose mode is enabled
log "Using EXT_DEVICE: $EXT_DEVICE"

# Configures the serial port using the stty command
log "Setting up the connection to the external device..."
stty -F "$EXT_DEVICE" 115200 cs8 -cstopb -parenb -icrnl -ixon -ixoff -opost -isig -icanon -echo

# receivers off
echo 'ATS4=92000700' > "$EXT_DEVICE"
sleep 1
# Power-ON Reset
echo 'ATS0=30000000' > "$EXT_DEVICE"
# Write config registers
#echo 'ATS1=FF0F5540' > "$EXT_DEVICE"
echo 'ATS1=FF0F1540' > "$EXT_DEVICE"
echo 'ATS0=80000004' > "$EXT_DEVICE"
echo 'ATS1=0D03C053' > "$EXT_DEVICE"
echo 'ATS0=84000004' > "$EXT_DEVICE"
echo 'ATS1=A113000A' > "$EXT_DEVICE"
echo 'ATS0=88000004' > "$EXT_DEVICE"
echo 'ATS1=CCCCF17D' > "$EXT_DEVICE"
echo 'ATS0=8C000004' > "$EXT_DEVICE"
echo 'ATS1=00000000' > "$EXT_DEVICE"
echo 'ATS0=90000001' > "$EXT_DEVICE"
# set T period to 10s
# echo 'ATS5=03B9ACA0' > "$EXT_DEVICE"
# set T period to 120s
echo 'ATS5=2CAD080' > "$EXT_DEVICE"
# Initialization reset
echo 'ATS0=18000000' > "$EXT_DEVICE"
# receivers on
echo 'ATS4=9200071F' > "$EXT_DEVICE"
