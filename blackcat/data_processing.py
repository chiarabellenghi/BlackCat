"""
Contains the Python implementation of a bunch of utility C-scripts.

They are meant to allow the user to unpack and process binary files and output
human-readable data.
Apologies for the hard-coded numbers. These are just meant as utility scripts.
Feel free to write your own version of these functions.

(C-code originally by Michael Boehmer for the BlackCat project).
"""

import sys
from collections.abc import Generator
from typing import BinaryIO

import numpy as np
import pandas as pd

# For BlackCat TDCs
TDC_FREQ = 340.0
FT_UNIT = 1000000.0 / TDC_FREQ
EPOC_UNIT = 4096.0 * 1000.0 / TDC_FREQ
BLOCK_RAM_SIZE = 512

# for external usb TDCs
COARSE_UNIT = 200000.0  # ps
EPOC_UNIT = (262144 * COARSE_UNIT) / 1000.0  # ns

MAX_TDC_CHANNEL = 4
TEMP_CHANNEL = 4

I2C_MAX31726 = 0x9E
I2C_LM75B = 0x92
I2C_LM75B_SCALE = 0.125
I2C_LM75B_DIVISOR = 32
I2C_MAX31726_SCALE = 0.00390625
MESSAGE_OK = 0x4F4B0D0A


def process_raw_cal(infile: str, outfile: str, verbose: bool = False) -> None:
    """Process a raw calibration file.

    Generates a human-readable calibration data file.

    Args:
        infile (str): Path to the input raw calibration file.
        outfile (str): Path to the output calibration data file.
        verbose (bool): If True, prints additional information during processing.
    """
    try:
        if verbose:
            print(f"Starting processing of raw calibration file: {infile}")
            print(f"Output will be written to: {outfile}")
        # Initialize histogram
        entries = np.zeros(BLOCK_RAM_SIZE, dtype=int)

        # First pass: Read input file and calculate sum and raw_bin
        with open(infile) as fin:
            for line in fin:
                value = int(line.strip(), 0)
                # Extract bits 20-28 from value and shift them to the
                # least significant bit (lsb) position.
                bin_num = (value & 0x1FF00000) >> 20
                # Extract bits 0-17 from value and store them as the entry.
                entry = value & 0x0003FFFF
                entries[bin_num] = entry

        # Calculate bin_lsb
        sum_entries = sum(entries)
        bin_lsb = FT_UNIT / sum_entries if sum_entries != 0 else 0.0

        # Second pass: Write output
        summed = 0.0
        with open(outfile, "w") as fout:
            # Write the # SUM line
            fout.write(
                f"# SUM {sum_entries:10d} {FT_UNIT:10.5f} {bin_lsb:10.5e}\n\n"
            )

            # Write the header line
            fout.write("BIN   ENTRIES   BIN_WIDTH   BIN_CENTER   BIN_SUM\n")

            # Process bins and write results
            for i in range(len(entries)):
                bin_width = entries[i] * bin_lsb
                summed += bin_width
                bin_center = summed - 0.5 * bin_width
                fout.write(
                    f"{i:4d} {entries[i]:8d} {bin_width:10.5f} {bin_center:10.5f} {summed:10.5f}\n"
                )

        if verbose:
            print("Processing completed successfully.\n")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        raise


def load_calibration_file(cal_file: str) -> pd.DataFrame:
    """Load the calibration file into a pandas DataFrame.

    Args:
        cal_file (str): Path to the calibration file.

    Returns
    -------
        pd.DataFrame: DataFrame containing the calibration data.

    Raises
    ------
        ValueError: If the number of bins is incorrect.
        FileNotFoundError: If the file is invalid.
    """
    try:
        # Use pandas to read the calibration file, skipping the first two lines
        df = pd.read_csv(
            cal_file,
            sep=r"\s+",
            skiprows=2,
            header=0,
        )

        # Ensure the number of bins matches BLOCK_RAM_SIZE
        if len(df) != BLOCK_RAM_SIZE:
            raise ValueError(
                f"Calibration file must contain exactly {BLOCK_RAM_SIZE} bins."
            )

        return df

    except FileNotFoundError:
        raise FileNotFoundError(f"Calibration file '{cal_file}' not found.")
    except Exception as e:
        raise ValueError(f"Error parsing calibration file: {e}.")


def read_longwords(file: BinaryIO) -> Generator[int, None, None]:
    """Read 4-byte longwords from the file and yield them as integers.

    Args:
        file (BinaryIO): The binary file to read from.

    Yields
    ------
        int: The next 4-byte longword as an integer.

    Raises
    ------
        EOFError: If fewer than 4 bytes are read.
    """
    while True:
        data_bytes = file.read(4)
        if len(data_bytes) != 4:
            break
        yield int.from_bytes(data_bytes, byteorder="big")


def unpack_dlm_data(
    cal_file: str,
    infile: str,
    period: int = 10000000,
    outfile: str = None,
    verbose: bool = False,
) -> None:
    """Unpack DLM data from a binary file using a calibration file.

    Args:
        cal_file (str): Path to the calibration file.
        input_file (str): Path to the binary input file.
        period (int): Period between DLMs in [ns]. Defaults to 10ms.
        outfile (str): Path to the output file. If None, prints to stdout.
        verbose (bool): If True, prints additional information during
            processing.
    """
    if verbose:
        print("\nStarting unpacking of DLM data.")
        print(f"Calibration file: {cal_file}")
        print(f"Input file: {infile}")
        if outfile:
            print(f"Output file: {outfile}")
        else:
            print("Output will be printed to stdout.")
        print(f"Expected DLM period: {period} ns")

    # Load the calibration file
    calibration_data = load_calibration_file(cal_file)
    lut_ft = calibration_data["BIN_CENTER"].values

    if verbose:
        print(
            "\nCalibration data loaded successfully. Number of bins: "
            f"{len(lut_ft)}"
        )

    dlm_period = float(period)
    epoc_raw = 0
    first_hit = True
    # state = {"epoc_raw": 0, "first_hit": True}

    def process_epoch(dataword: int, epoc_raw: int, first_hit: bool):
        """Process an epoch word and calculate the epoch difference.

        Returns
        -------
            Tuple[int, float, bool]: Updated epoc_raw_old, epoch difference in
                ns, and first_hit flag.
        """
        epoc = dataword & 0x0FFFFFFF

        if first_hit:
            return epoc, 0.0, False

        epoc_diff_int = epoc - epoc_raw
        if epoc_diff_int < 0:
            epoc_diff_int += 1 << 28
        epoc_diff = epoc_diff_int * EPOC_UNIT

        return epoc, epoc_diff, first_hit

    def process_hit(dataword: int):
        """Process a hit word and calculates the corrected time.

        Returns
        -------
            Tuple[int, float]: The channel number and corrected time.
        """
        ch = (dataword & 0x1FC00000) >> 22
        ct = (dataword & 0x000007FF) << 1
        if dataword & 0x00200000:
            ct += 1
        ft = (dataword & 0x001FF000) >> 12

        fine = lut_ft[ft] / 1000.0
        coarse = ct * 1000.0 / TDC_FREQ
        corrected_time = coarse - fine

        return ch, corrected_time

    # def process_dataword(
    #     dataword,
    #     longwords,
    #     fout,
    #     verbose,
    #     dlm_period,
    #     lut_ft,
    #     state,
    # ):
    #     """Process a single dataword and handle output.

    #     Helper function.
    #     """
    #     # The first longword should be an epoch (no msb)
    #     if dataword & 0x80000000:
    #         if verbose:
    #             print("# WARNING: WRONG STRUCTURE (0) - HIT FOUND")
    #         return

    #     # Process epoch
    #     epoc_raw, epoc_diff, first_hit = process_epoch(
    #         dataword, state["epoc_raw"], state["first_hit"]
    #     )
    #     # Update state
    #     state["epoc_raw"] = epoc_raw
    #     state["first_hit"] = first_hit

    #     if first_hit:
    #         return

    #     if dlm_period * 0.95 < epoc_diff <= dlm_period * 1.05:
    #         mode = 0
    #     elif 2 * dlm_period * 0.95 < epoc_diff <= 2 * dlm_period * 1.05:
    #         mode = 1
    #     else:
    #         mode = -1

    #     # Fetch first hit
    #     dataword = next(longwords)
    #     if not (dataword & 0x80000000):
    #         raise ValueError("Wrong structure: EPOC found")

    #     ch_a, hit_a = process_hit(dataword)

    #     # Maybe fetch new epoc before second hit
    #     dataword = next(longwords)
    #     if not (dataword & 0x80000000):
    #         epoc_raw, epoc_diff, first_hit = process_epoch(
    #             dataword, state["epoc_raw"], state["first_hit"]
    #         )
    #         state["epoc_raw"] = epoc_raw
    #         state["first_hit"] = first_hit
    #         dataword = next(longwords)

    #     ch_b, hit_b = process_hit(dataword)

    #     if ch_a == ch_b:
    #         delta_t = hit_b - hit_a
    #         if delta_t < 0:
    #             delta_t += EPOC_UNIT
    #         output_line = f"{ch_a:2} {delta_t:11.5f} {mode}"
    #         if fout:
    #             fout.write(output_line + "\n")
    #         else:
    #             print(output_line)

    #     else:
    #         raise ValueError("Channel mixup detected")

    # try:
    #     with open(infile, "rb") as fin:
    #         longwords = read_longwords(fin)
    #         try:
    #             if outfile:
    #                 with open(outfile, "w") as fout:
    #                     for dataword in longwords:
    #                         process_dataword(
    #                             dataword,
    #                             longwords,
    #                             fout,
    #                             verbose,
    #                             dlm_period,
    #                             lut_ft,
    #                             state,
    #                         )
    #             else:
    #                 # Print directly to stdout
    #                 for dataword in longwords:
    #                     process_dataword(
    #                         dataword,
    #                         longwords,
    #                         None,
    #                         verbose,
    #                         dlm_period,
    #                         lut_ft,
    #                         state,
    #                     )

    #         except StopIteration:
    #             if verbose:
    #                 print("# End of file reached")

    #     if verbose:
    #         print("\nUnpacking completed successfully.")

    # except FileNotFoundError as e:
    #     print(f"Error: {e}")
    #     raise
    # except ValueError as e:
    #     print(f"Error: {e}")
    #     raise

    try:
        with (
            open(infile, "rb") as fin,
            open(outfile, "w") if outfile else None as fout,
        ):
            longwords = read_longwords(fin)

            try:
                for dataword in longwords:
                    # The first longword should be an epoch (no msb)
                    if dataword & 0x80000000:
                        if verbose:
                            print("# WARNING: WRONG STRUCTURE (0) - HIT FOUND")
                        continue

                    # Process epoch
                    epoc_raw, epoc_diff, first_hit = process_epoch(
                        dataword, epoc_raw, first_hit
                    )

                    if first_hit:
                        continue

                    if dlm_period * 0.95 < epoc_diff <= dlm_period * 1.05:
                        mode = 0
                    elif (
                        2 * dlm_period * 0.95
                        < epoc_diff
                        <= 2 * dlm_period * 1.05
                    ):
                        mode = 1
                    else:
                        mode = -1

                    # Read and process the first hit
                    dataword = next(longwords)
                    if not (dataword & 0x80000000):
                        raise ValueError("Wrong structure: EPOC found")

                    ch_a, hit_a = process_hit(dataword)

                    # Read and process the second hit
                    dataword = next(longwords)

                    if not (dataword & 0x80000000):
                        epoc_raw, epoc_diff, first_hit = process_epoch(
                            dataword, epoc_raw, first_hit
                        )
                        dataword = next(longwords)

                    ch_b, hit_b = process_hit(dataword)

                    if ch_a == ch_b:
                        delta_t = hit_b - hit_a
                        if delta_t < 0:
                            delta_t += EPOC_UNIT
                        output_line = f"{ch_a:2} {delta_t:11.5f} {mode}"
                        if fout:
                            fout.write(output_line + "\n")
                        else:
                            print(output_line)
                    else:
                        raise ValueError("Channel mixup detected")

            except StopIteration:
                if verbose:
                    print("# End of file reached")

            finally:
                if fout:
                    fout.close()
        if verbose:
            print("\nUnpacking completed successfully.")

    except FileNotFoundError as e:
        print(f"Error: {e}")
        raise
    except ValueError as e:
        print(f"Error: {e}")
        raise


def average_dlm_data(
    mean_expected: int,
    infile: str = None,
    outfile: str = None,
    n_channels: int = 10,
    verbose: bool = False,
) -> None:
    """
    Analyzes fine time data from an input text file.

    Args:
        mean_expected (int): Expected number of hits per mean value.
        infile (str): Path to the input file containing fine time data.
            If None, reads from stdin.
        outfile (str): Path to the output file. If None, prints to stdout.
        n_channels (int): Number of channels expected. Defaults to 10.
        verbose (bool): If True, prints debug information.

    Raises
    ------
        ValueError: If input parameters are invalid or data is inconsistent.
    """
    if mean_expected <= 0:
        raise ValueError("mean_expected must be a positive integer")

    # Read input lines
    if infile is None:
        lines = sys.stdin.readlines()
    else:
        with open(infile) as f:
            lines = f.readlines()

    data = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        columns = line.split()
        if len(columns) < 2:
            continue
        try:
            channel = int(columns[0])
            delay = float(columns[1])
            data.append((channel, delay))
        except ValueError:
            continue

    results = []
    buffer = []
    tmp = []
    prev_channel = data[0][0]
    data_ok = False
    skipped_entries = 0

    def flush_hist():
        if len(tmp) == n_channels:
            results.append(" ".join(f"{c} {v:.5f}" for c, v in tmp))
        else:
            raise ValueError(
                f"Expected {n_channels} channels in hist, got {len(tmp)}"
            )

    for channel, delay in data:
        # Check channel rollover
        if channel != prev_channel:
            if data_ok and len(buffer) == mean_expected:
                avg = sum(d for _, d in buffer) / mean_expected
                tmp.append((prev_channel, avg))
            else:
                skipped_entries += len(buffer)

            # Output when rollover and data_ok
            if data_ok and channel < prev_channel:
                flush_hist()
                tmp.clear()
            elif not data_ok and channel < prev_channel:
                data_ok = True
                if verbose:
                    print(
                        f"# INFO: SKIPPED {skipped_entries} ENTRIES, MEAN EXPECTED = {mean_expected}",
                    )
                tmp.clear()

            buffer = [(channel, delay)]
            prev_channel = channel
        else:
            # Otherwise, just append to the buffer
            buffer.append((channel, delay))

        if len(buffer) == mean_expected and data_ok:
            # when the buffer is full, calculate the avg
            avg = sum(d for _, d in buffer) / mean_expected
            tmp.append((channel, avg))
            buffer = []

    # Handle the last buffer
    if data_ok and len(tmp) == n_channels:
        flush_hist()

    # Write output
    if outfile:
        with open(outfile, "w") as f:
            for line in results:
                f.write(line + "\n")
    else:
        for line in results:
            print(line)


def decode_usb_tdc(
    infile: BinaryIO,
    dlm_period_ns: int,
    max_diff_ns: int,
    skip_events: int = 0,
    verbose: bool = False,
    outfile: str | None = None,
) -> None:
    """
    Decode USB binary data and process timing information.

    Args:
        infile (BinaryIO): The binary input file containing USB smart data.
        dlm_period_ns (int): The delimiter period in nanoseconds.
        max_diff_ns (int): The maximum allowable time difference in ns.
        skip_events (int, optional): The number of initial events to skip.
            Defaults to 0.
        verbose (bool, optional): If True, enables verbose output.
            Defaults to False.
        outfile (str | None, optional): The path to the output file.
            If None, results are printed to the console.

    Returns
    -------
        None: This function does not return a value. It writes results to a file or prints them to the console.
    """

    def read_40bit_word(fin):
        raw = fin.read(5)
        if len(raw) != 5:
            return None
        return int.from_bytes(raw, "big")

    def output(line: str):
        print(line, file=out) if out else print(line)

    def emit_time_differences(times, mode):
        parts = []
        for i in range(len(times), 0, -1):
            for j in range(i - 1):
                diff = times[i - 1] - times[j]
                if abs(diff) > 11_000:
                    diff -= EPOC_UNIT if diff > 0 else -EPOC_UNIT
                if abs(diff) > 11_000:
                    raise ValueError(f"Time diff overflow: {diff:.4f}")
                parts.append(f"{i - 1}.{j} {abs(diff):11.5f}")
        parts.append(str(mode))
        output(" ".join(parts))

    def emit_placeholder_block(mode):
        parts = [
            f"{i - 1}.{j} {0.0:11.5f}"
            for i in range(MAX_TDC_CHANNEL, 0, -1)
            for j in range(i - 1)
        ]
        parts.append(str(mode))
        output(" ".join(parts))

    # Open output file if needed
    out = open(outfile, "w") if outfile else None

    try:
        with open(infile, "rb") as fin:
            # Check for optional OK\r\n header
            header = int.from_bytes(fin.read(4), "big")
            if header != MESSAGE_OK:
                fin.seek(0)

            # Setup state
            tdc_time_history = [0.0] * MAX_TDC_CHANNEL
            tdc_hit_count = [0] * MAX_TDC_CHANNEL
            tdc_counter = 0
            old_tdc_time = 0.0
            first_hit = True

            dlm_period = float(dlm_period_ns)
            dlm_diff = float(max_diff_ns)

            while True:
                dataword = read_40bit_word(fin)
                if dataword is None:
                    break

                channel = (dataword >> 36) & 0xF

                # --- TDC Hit ---
                if channel < MAX_TDC_CHANNEL:
                    coarse = (dataword >> 18) & 0x3FFFF
                    fine = dataword & 0x3FFFF
                    if fine > COARSE_UNIT:
                        raise ValueError("Invalid fine time.")

                    tdc_time = (coarse * COARSE_UNIT + fine) / 1000.0

                    if first_hit:
                        time_diff = -1
                        first_hit = False
                    else:
                        time_diff = tdc_time - old_tdc_time
                        if time_diff < 0:
                            time_diff += (
                                EPOC_UNIT if abs(time_diff) > dlm_diff else 0
                            )
                        else:
                            time_diff = abs(time_diff)

                    old_tdc_time = tdc_time

                    # Classify DLM mode
                    if time_diff <= dlm_diff * 1.10:
                        tdc_hit_count[channel] += 1
                        tdc_time_history[channel] = tdc_time
                        tdc_counter += 1
                        continue
                    elif dlm_period * 0.90 < time_diff <= dlm_period * 1.10:
                        mode = 0  # MD_PERIOD
                    elif (
                        2 * dlm_period * 0.90
                        < time_diff
                        <= 2 * dlm_period * 1.10
                    ):
                        mode = 1  # MD_LONG_PERIOD
                    elif time_diff <= dlm_period * 0.90:
                        if verbose:
                            print("# INFO: Spurious hit between blocks")
                        continue
                    else:
                        continue  # Unknown timing

                    # Emit block
                    if tdc_counter == MAX_TDC_CHANNEL:
                        if skip_events:
                            skip_events -= 1
                            if verbose:
                                print("# INFO: Skipped block")
                        elif all(c == 1 for c in tdc_hit_count):
                            emit_time_differences(tdc_time_history, mode)
                        else:
                            if verbose:
                                print("# INFO: Multiple hits detected")
                            emit_placeholder_block(mode)
                    else:
                        if verbose:
                            print(f"# INFO: Incomplete block ({tdc_counter})")
                        emit_placeholder_block(mode)

                    # Reset
                    tdc_time_history = [0.0] * MAX_TDC_CHANNEL
                    tdc_hit_count = [0] * MAX_TDC_CHANNEL
                    tdc_counter = 0

                    # Start new block
                    tdc_hit_count[channel] += 1
                    tdc_time_history[channel] = tdc_time
                    tdc_counter += 1

                # --- Temperature ---
                elif channel == TEMP_CHANNEL:
                    i2c_addr = (dataword >> 24) & 0xFF
                    i2c_status = (dataword >> 16) & 0xFF
                    i2c_data = dataword & 0xFFFF
                    temp = -66.6666

                    if i2c_status == 0:
                        if i2c_addr == I2C_MAX31726:
                            temp = i2c_data * I2C_MAX31726_SCALE
                            label = "MAX31726"
                        elif i2c_addr == I2C_LM75B:
                            temp = (
                                i2c_data // I2C_LM75B_DIVISOR
                            ) * I2C_LM75B_SCALE
                            label = "LM75B"
                        else:
                            label = "unknown I2C"
                    else:
                        label = "error"

                    output(f"{temp:8.4f} # TMP {label}")

                # --- Error ---
                elif channel > MAX_TDC_CHANNEL:
                    raise ValueError(f"Broken channel: 0x{dataword:010x}")

    finally:
        if out:
            out.close()


def average_usb_tdc_data(
    mean_expected: int,
    infile: str = None,
    outfile: str = None,
    verbose: bool = False,
) -> None:
    """
    Averages delay values from a USB TDC decoded text file.

    Args:
        mean_expected (int): Number of events to average over.
        infile (str): Input file path. If None, reads from stdin.
        outfile (str): Output file path. If None, writes to stdout.
        verbose (bool): If True, prints per-channel min/max/diff info.
    """
    import sys

    import numpy as np

    input_opener = open(infile) if infile else sys.stdin
    output_opener = open(outfile, "w") if outfile else sys.stdout

    with input_opener as input_stream, output_opener as output_stream:

        def emit(line: str):
            print(line, file=output_stream)

        # Step 1: Read the first valid line to infer number of pairs
        for raw_line in input_stream:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) < 3 or (len(parts) - 1) % 2 != 0:
                continue
            num_pairs = (len(parts) - 1) // 2
            first_line = parts
            break
        else:
            raise ValueError("No valid data lines found in input.")

        # Step 2: Initialize state
        data_read = data_valid = 0
        sums = np.zeros(num_pairs, dtype=np.float64)
        diff_min = np.full(num_pairs, np.inf, dtype=np.float64)
        diff_max = np.zeros(num_pairs, dtype=np.float64)
        ch_labels = [None] * num_pairs

        def process(parts):
            nonlocal data_read, data_valid, sums
            try:
                diffs = np.empty(num_pairs, dtype=np.float64)
                for i in range(num_pairs):
                    label, val = parts[2 * i], float(parts[2 * i + 1])
                    if ch_labels[i] is None:
                        ch_labels[i] = label
                    diffs[i] = val
                total = diffs.sum()
            except Exception:
                return  # skip malformed line

            data_read += 1
            if total > 0.0:
                data_valid += 1
                sums += diffs

            if data_read == mean_expected:
                means = (
                    sums / data_valid if data_valid > 0 else np.zeros_like(sums)
                )
                output_parts = [
                    f"{ch_labels[i]} {means[i]:11.5f}" for i in range(num_pairs)
                ]
                emit("  ".join(output_parts))

                valid_mask = means > 0.0
                diff_min[valid_mask] = np.minimum(
                    diff_min[valid_mask], means[valid_mask]
                )
                diff_max[valid_mask] = np.maximum(
                    diff_max[valid_mask], means[valid_mask]
                )

                data_read = data_valid = 0
                sums.fill(0.0)

        # Step 3: Process first and remaining lines
        process(first_line)

        for raw_line in input_stream:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) != 2 * num_pairs + 1:
                continue
            process(parts)

        if verbose:
            for i in range(num_pairs):
                emit(f"# MIN {i} {diff_min[i]:11.5f}")
                emit(f"# MAX {i} {diff_max[i]:11.5f}")
                emit(f"# DIF {i} {diff_max[i] - diff_min[i]:11.5f}")
