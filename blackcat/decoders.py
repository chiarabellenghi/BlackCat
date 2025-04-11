################################################################################
# This file contains the Python implementation of a bunch of utility C-scripts
# written by Michael Boehmer for the BlackCat project. They are meant to allow
# the user to convert the output of DOGMA into a human readable format.
################################################################################
import numpy as np

# Period of one ref clock cycle of TDC in ps
FT_UNIT = 1000000.0 / 340.0
BLOCK_RAM_SIZE = 512


def process_raw_cal(infile: str, outfile: str) -> None:
    """
    Processes a raw calibration file and generates a calibration data file.

    Args:
        infile (str): Path to the input raw calibration file.
        outfile (str): Path to the output calibration data file.
    """
    try:
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
            fout.write(
                "# BIN NUM   ENTRIES   BIN WIDTH [ps]   BIN CENTER [ps]   BIN SUM [ps]\n"
            )

            # Process bins and write results
            for i in range(len(entries)):
                bin_width = entries[i] * bin_lsb
                summed += bin_width
                bin_center = summed - 0.5 * bin_width
                fout.write(
                    f"{i:4d} {entries[i]:8d} {bin_width:10.5f} {bin_center:10.5f} {summed:10.5f}\n"
                )

    except FileNotFoundError as e:
        print(f"Error: {e}")
        raise
