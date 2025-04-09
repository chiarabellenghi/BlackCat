import argparse
import time
from blackcat import BlackCat

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the DLM script for BlackCat system."
    )
    parser.add_argument(
        "--base-dir",
        "-b",
        type=str,
        default="/home/trbnet/pone-crate/chiara/blackcat",
        help="Base directory where the bash scripts are located. "
        "Default is /home/trbnet/pone-crate/chiara/blackcat.",
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
        "--time",
        "-t",
        type=float,
        default=None,
        help="Time to wait for the measurement (in seconds). "
        "If not set, measurement will run until interrupted manually.",
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
    blackcat = BlackCat(args.base_dir, args.config_file)

    # Run setup and calibration
    print("\nRun setup and calibration")
    blackcat.setup_and_calibrate(verbose=args.verbose)

    # Setup listener ports and start measurement
    print("\nSetup listener ports and start measurement")
    blackcat.run_link_delay_measurement(verbose=args.verbose)

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
    blackcat.stop_measurement(verbose=args.verbose)

    print("Done!")
