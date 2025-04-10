#!/bin/bash

# Send the broadcast ping
ping 10.1.1.255 -b -p abad1deab4000000 -c 1 -w 1 || true