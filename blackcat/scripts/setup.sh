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

# Ensure the configuration file exists
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

# Read TOMcat and TDC IDs from the [setup] section of the configuration file
# TOMCAT_IDS=$(awk -F '=' '/tomcat_ids/ {print $2}' "$CONFIG_FILE" | tr ' ' '\n')
# TDC_IDS=$(awk -F '=' '/tdc_ids/ {print $2}' "$CONFIG_FILE" | tr ' ' '\n')
TOMCAT_IDS=$(awk -F '=' '/tomcat_ids/ {print $2}' "$CONFIG_FILE" | cut -d '=' -f2-)
TDC_IDS=$(awk -F '=' '/tdc_ids/ {print $2}' "$CONFIG_FILE" | cut -d '=' -f2-)

if [ -z "$TOMCAT_IDS" ] || [ -z "$TDC_IDS" ]; then
    echo "Error: TOMcat or TDC IDs not found in the configuration file."
    exit 1
fi

log "TOMcat IDs: $(echo $TOMCAT_IDS | tr '\n' ' ')"
log "TDC IDs: $(echo $TDC_IDS | tr '\n' ' ')"

# Convert strings to space-separated ID lists
TOMCAT_IDS=$(echo "$TOMCAT_IDS_LINE" | xargs)
TDC_IDS=$(echo "$TDC_IDS_LINE" | xargs)

# address setup: we assign TOMcat bit 0 in multicast2 mode
log "Setting up TOMcat addresses..."
for id in $TOMCAT_IDS; do
    DOGMA_IP=10.1.1.$id dog write 0xff000000 34 0xfe000001
    DOGMA_IP=10.1.1.$id dog write 0xff000000 32 $id
done

# all modules with TDC get bit 1 in multicast2 mode
# the MST module gets bit 23 in multicast2 mode
# the SLV modules get bit 22 in multicast2 mode
log "Setting up multicast2 mode for TDC modules..."
for id in $TDC_IDS; do
    if [ "$id" == "150" ]; then
        DOGMA_IP=10.1.1.$id dog write 0xff000000 34 0xfe800002
    else
        DOGMA_IP=10.1.1.$id dog write 0xff000000 34 0xfe400002
    fi
    DOGMA_IP=10.1.1.$id dog write 0xff000000 32 $id
done

# check things
if [ "$VERBOSE" -eq 1 ]; then
    dog -b read 0xff000000 32
    dog -b read 0xff000000 34
fi

# disable DLMs (all modules)
log "Disabling DLMs (delay link measurements)..."
dog -b write 0xff000000 136 0x00800000

# set DLM frequency (10ms) and ticker mark (77)
log "Setting DLM frequency and ticker mark..."
dog -b write 0xff000000 135 0x4d098968

# TX enable for DLMs (non-ROOT modules)
log "Enabling transmission for DLM..."
dog -b write 0xfe400001 128 0x0000ffff
# TX enable for DLMs (ROOT module)
dog -b write 0xfe800000 128 0x0000efff

# check things
if [ "$VERBOSE" -eq 1 ]; then
    dog -b read 0xff000000 128
fi

log "Set destination for TDC data"
# set destination MAC/PORT
# 150 => 22222
dog -b sequence-write 150 141 0x0416466e 0x56ce241c 0x0a010101
# 152 => 22223
dog -b sequence-write 152 141 0x0416466e 0x56cf241c 0x0a010101
# 154 => 22224
dog -b sequence-write 154 141 0x0416466e 0x56d0241c 0x0a010101

# enable triggered DLMs
log "Enabling triggered DLMs..."
dog -b write 150 136 0x40800000
# reset TDC
log "Resetting TDC..."
dog -b write 150 2 0x000400d0
dog -b write 150 2 0x000400de
dog -b write 150 2 0x000400df
dog -b write 150 2 0x000400d1

# enable pushers
log "Enabling pushers..."
dog -b write 0xfe000002 133 0x77f00000

# check settings
if [ "$VERBOSE" -eq 1 ]; then
    dog -b read 0xfe000002 141
    dog -b read 0xfe000002 142
    dog -b read 0xfe000002 143
fi
