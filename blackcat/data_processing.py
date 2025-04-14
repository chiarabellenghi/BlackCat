################################################################################
# This file contains the Python implementation of a bunch of utility C-scripts
# written by Michael Boehmer for the BlackCat project. They are meant to allow
# the user to unpack and process binary files and output human-readable data.
# Apologies for the large amount of hard-coded numbers. These are just meant as
# utility scripts. Feel free to write your own version of these functions.
################################################################################
import numpy as np
import pandas as pd
from typing import Generator, BinaryIO

# Period of one ref clock cycle of TDC in ps
TDC_FREQ = 340.0
FT_UNIT = 1000000.0 / TDC_FREQ
BLOCK_RAM_SIZE = 512

EPOC_UNIT = 4096.0 * 1000.0 / TDC_FREQ


def process_raw_cal(infile: str, outfile: str, verbose: bool = False) -> None:
    """
    Processes a raw calibration file and generates a calibration data file.

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
        with open(infile, "r") as fin:
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
    """
    Loads the calibration file into a pandas DataFrame and validates the number of bins.

    Args:
        cal_file (str): Path to the calibration file.

    Returns:
        pd.DataFrame: DataFrame containing the calibration data.

    Raises:
        ValueError: If the number of bins is incorrect.
        FileNotFoundError: If the file is invalid.
    """
    try:
        # Use pandas to read the calibration file, skipping the first two lines
        df = pd.read_csv(
            cal_file,
            sep="\s+",
            skiprows=2,
            header=0,
            # names=["BIN", "ENTRIES", "BIN_WIDTH", "BIN_CENTER", "BIN_SUM"],
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
    """
    Reads 4-byte longwords from the file and yields them as integers.

    Args:
        file (BinaryIO): The binary file to read from.

    Yields:
        int: The next 4-byte longword as an integer.

    Raises:
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
    period: int = 6666666,
    outfile: str = None,
    verbose: bool = False,
) -> None:
    """
    Unpacks DLM data from a binary file using a calibration file.

    Args:
        cal_file (str): Path to the calibration file.
        input_file (str): Path to the binary input file.
        period (int): Period between DLMs in [ns].
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

    def process_epoch(dataword: int, epoc_raw: int, first_hit: bool):
        """
        Processes an epoch word and calculates the epoch difference.

        Returns:
            Tuple[int, float, bool]: Updated epoc_raw_old, epoch difference in
                ns, and first_hit flag.
        """
        epoc = dataword & 0x0FFFFFFF

        if first_hit:
            if verbose:
                print("First epoch detected.")
            return epoc, 0.0, False

        epoc_diff_int = epoc - epoc_raw
        if epoc_diff_int < 0:
            epoc_diff_int += 1 << 28
        epoc_diff = epoc_diff_int * EPOC_UNIT

        return epoc, epoc_diff, first_hit

    def process_hit(dataword: int):
        """
        Processes a hit word and calculates the corrected time.

        Returns:
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

    try:
        with open(infile, "rb") as fin:
            longwords = read_longwords(fin)

            # Open the output file if provided, otherwise use None
            fout = open(outfile, "w") if outfile else None

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
                        mode = "Single"
                    elif (
                        2 * dlm_period * 0.95
                        < epoc_diff
                        <= 2 * dlm_period * 1.05
                    ):
                        mode = "Long"
                    else:
                        mode = "Unknown"

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


# def analyze_fine_time(
#     infile: str, mean_expected: int, outfile: str = None, verbose: bool = False
# ) -> None:
#     """
#     Analyzes fine time data from an input file.

#     Args:
#         infile (str): Path to the input file containing fine time data.
#         mean_expected (int): Expected number of hits per mean value.
#         outfile (str): Path to the output file. If None, prints to stdout.
#         verbose (bool): If True, prints debug information.

#     Raises:
#         ValueError: If input parameters are invalid or data is inconsistent.
#     """
#     if mean_expected <= 0:
#         raise ValueError("Mean expected must be greater than 0.")

#     try:
#         # Load the input file into a pandas DataFrame
#         df = pd.read_csv(
#             infile,
#             sep="\s+",
#             header=None,
#             names=["Channel", "Delay", "Period"],
#             usecols=["Channel", "Delay"],  # Only parse the first two columns
#             dtype={"Channel": int, "Delay": float},
#         )

#         if verbose:
#             print(f"Loaded {len(df)} rows from {infile}.")

#         # Open the output file if provided, otherwise use stdout
#         fout = open(outfile, "w") if outfile else None

#     except FileNotFoundError:
#         raise FileNotFoundError(f"Input file '{infile}' not found.")
#     except Exception as e:
#         raise ValueError(f"Error processing file: {e}")
