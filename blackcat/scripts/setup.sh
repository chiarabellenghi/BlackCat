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

log "CONFIG_FILE $CONFIG_FILE"

BASE_IP=$(hostname -I | awk '{print $1}' | sed -E 's/\.[0-9]+$//')
log "Detected base IP: $BASE_IP"

# Read TOMcat and TDC IDs from the [setup] section of the configuration file
TOMCAT_IDS=$(awk -F '=' '/tomcat_ids/ {print $2}' "$CONFIG_FILE" | tr ' ' '\n')
TDC_IDS=$(awk -F '=' '/tdc_ids/ {print $2}' "$CONFIG_FILE" | tr ' ' '\n' | grep -v '^$')

if [ -z "$TDC_IDS" ]; then
	echo "Error: TDC IDs not found in the configuration file."
	exit 1
fi

log "TDC IDs: $(echo $TDC_IDS | tr '\n' ' ')"

if [ -z "$TOMCAT_IDS" ]; then
	log "No TOMcat IDs found. Skipping TOMcat setup..."
else
	# address setup: we assign TOMcat bit 0 in multicast2 mode
	log "TOMcat IDs: $(echo $TOMCAT_IDS | tr '\n' ' ')"
	for id in $TOMCAT_IDS; do
		DOGMA_IP=$BASE_IP.$id dog write 0xff000000 34 0xfe000001
		DOGMA_IP=$BASE_IP.$id dog write 0xff000000 32 $id
	done
fi

# Convert to array
mapfile -t TDC_ARRAY < <(echo "$TDC_IDS")
LDR_TDC_ID="${TDC_ARRAY[0]}"
FLW_TDC_IDS=("${TDC_ARRAY[@]:1}")

# all modules with TDC get bit 1 in multicast2 mode
log "Setting up multicast2 mode for TDC modules..."

# Configure leader (gets bit 23 in multicast2 mode)
DOGMA_IP=$BASE_IP.$LDR_TDC_ID dog write 0xff000000 34 0xfe800002
DOGMA_IP=$BASE_IP.$LDR_TDC_ID dog write 0xff000000 32 $LDR_TDC_ID

# Configure followers (get bit 22 in multicast2 mode)
for id in "${FLW_TDC_IDS[@]}"; do
    DOGMA_IP=$BASE_IP.$id dog write 0xff000000 34 0xfe400002
    DOGMA_IP=$BASE_IP.$id dog write 0xff000000 32 $id
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
dog -b write 0xff000000 135 0x00098967 # 8ns DLM  pulse

# TX enable for DLMs (non-ROOT modules)
log "Enabling transmission for DLM..."
dog -b write 0xfe400000 128 0x0000ffff
# TX enable for DLMs (ROOT module)
dog -b write 0xfe800000 128 0x0000dfff
# TC only uplink
dog -b write 0xfe000001 128 0x00000001

# check things
if [ "$VERBOSE" -eq 1 ]; then
    dog -b read 0xff000000 128
fi

echo $TDC_IDS

log "Set destination for TDC data"
# set destination MAC/PORT
BASE_PORT_HEX=(0x56ce0a88 0x56d00a88 0x56d20a88)
i=0
for id in $TDC_IDS; do
    dog -b sequence-write "$id" 141 0xc184fe2a "${BASE_PORT_HEX[$i]}" 0x0a010101
    i=$((i + 1))
done

# enable triggered DLMs
log "Enabling triggered DLMs..."
dog -b write "$LDR_TDC_ID" 136 0x40800000
# reset TDC
log "Resetting TDC..."
dog -b write "$LDR_TDC_ID" 2 0x000400d0
dog -b write "$LDR_TDC_ID" 2 0x000400de
dog -b write "$LDR_TDC_ID" 2 0x000400df
dog -b write "$LDR_TDC_ID" 2 0x000400d1

# enable pushers
log "Enabling pushers..."
dog -b write 0xfe000002 133 0x67f00000

