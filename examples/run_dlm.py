import argparse
import time
from blackcat.core import BlackCat

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the DLM script for BlackCat system."
    )
    parser.add_argument(
        "--config-file",
        "-c",
        type=str,
        default="/home/trbnet/pone-crate/chiara/blackcat/config.cfg",
        help="Path to the configuration file. "
        "Default is /home/trbnet/pone-crate/chiara/blackcat/config.cfg.",
    )
    parser.add_argument(
        "--calibration",
        "-cal",
        action="store_true",
        help="Run calibration before starting the measurement. "
        "If not set, the measurement will run without calibration.",
    )
    parser.add_argument(
        "--time",
        "-t",
        type=float,
        default=None,
        help="Time to wait for the measurement (in seconds). "
        "If not set, measurement will run until interrupted manually.",
    )
    parser.add_argument(
        "--subdir",
        "-sd",
        type=str,
        default=None,
        help="Subdirectory for saving data. This is appended to the save path "
        "defined in the config file. It can be useful when running multiple "
        "measurements requiring a calibration each.",
    )
    parser.add_argument(
        "--outfile_suffix",
        "-o",
        type=str,
        default=None,
        help="Suffix for the output file name. It is attached to the default"
        "name in this way `data_<ch>_<suffix>.bin`. This can be useful when "
        "running multiple measurements with the same calibration.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output. Defaults to False.",
    )

    args = parser.parse_args()
    print(args)

    # Initialize BlackCat object
    print("\nInitialize BlackCat")
    blackcat = BlackCat(args.config_file, args.subdir)

    # Run setup and calibration (if specified)
    if args.calibration:
        print("\nRun setup and calibration")
        blackcat.setup_and_calibrate(verbose=args.verbose)
    else:
        print("\nRun setup without calibration")
        blackcat.setup(verbose=args.verbose)

    # Setup listener ports and start measurement
    print("\nSetup listener ports and start measurement")
    blackcat.run_link_delay_measurement(
        outfile_suffix=args.outfile_suffix, verbose=args.verbose
    )

    # Sleep for specified time, or run indefinitely
    if args.time:
        print(f"\nSleeping for {args.time} seconds")
        time.sleep(args.time)
    else:
        print("\nMeasurement running indefinitely. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nManual stop triggered. Stopping measurement...")

    # Stop the measurement
    print("\nStopping measurement")
    blackcat.stop_measurement()

    print("Done!")
