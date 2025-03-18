import os
from pathlib import Path
import configparser
import logging
from logger import configure_logging
from utils import run_shell_script
from decoders import process_raw_cal


class BlackCat(object):
    """This class is hopefully helpful to use the BlackCat system.
    With methods implemented for this object, you can setup the
    system, run calibration measurements, run round-trip link delay
    measurements.
    """

    def __init__(self, base_dir: str, config_file: str) -> None:
        """Initializes the object giving it a base directory where
        we are going to work and a config file.

        Args:
            base_dir (str): The base directory where the bash scripts are
                located.
            config_file (str): Path to the configuration file.

        Raises:
            FileNotFoundError: If the base directory does not exist or is
                not a directory.
        """
        # Initialize logger for this class
        configure_logging()
        self.logger = logging.getLogger(self.__class__.__name__)

        # Make sure the base directory exists. It has to be the directory
        # where the  bash scripts are
        self.base_dir = Path(base_dir).resolve()
        if not self.base_dir.exists() or not self.base_dir.is_dir():
            raise FileNotFoundError(
                f"INIT ERROR: Base directory '{self.base_dir}' does not exist."
            )

        os.chdir(self.base_dir)
        self.logger.info(f"INIT: Changed working directory to: {Path.cwd()}")

        # Read the config file
        self.config = configparser.ConfigParser()
        self.config_file = Path(config_file).resolve()
        if not self.config_file.exists():
            raise FileNotFoundError(
                f"INIT ERROR: Configuration file '{self.config_file}' does not exist."
            )
        self.config.read(self.config_file)

        self.logger.info(f"INIT: Loaded configuration from: {self.config_file}")

    def setup(self, verbose=False) -> None:
        """Sets up everything, assigning IDs and broadcast bits
        to all modules.

        Raises:
            KeyError: If the "setup" section or "script" key is missing in
                the config file.
        """
        script = self.config["setup"]["script"]
        arguments = ["--config_file", str(self.config_file)]
        if verbose:
            arguments = ["--verbose"]

        run_shell_script(
            script,
            arguments=arguments,
            logger=self.logger,
            process_name="SETUP",
        )

    def calibrate(self, verbose=False) -> None:
        """Runs the calibration. First get to the calibration directory
        for this runs. I have no clue what this will be in the final
        configuration of P-ONE-1, so let us keep it flexible for the
        moment. We read it out of the config file.

        Args:
            verbose (bool, optional): If True, adds a '--verbose' argument
                to the script. Defaults to False.

        Raises:
            KeyError: If the "calibration" section or "script" key is
                missing in the config file.
        """
        script = self.config["calibration"]["script"]
        arguments = ["--config_file", str(self.config_file)]
        if verbose:
            arguments.append("--verbose")

        run_shell_script(
            script,
            arguments=arguments,
            logger=self.logger,
            process_name="CALIBRATION",
        )

        # Process the raw calibration files
        self.process_raw_calibration(verbose=verbose)
        self.logger.info("CALIBRATION: DONE.")

    def process_raw_calibration(self, verbose=False) -> None:
        """
        Processes raw calibration files and generates human-readable calibration files.

        This method ensures that the output directory for calibration files exists,
        retrieves the list of TDC IDs from the configuration, and processes each raw
        calibration file (`rc_<id>`) into a human-readable format (`tdc_cal_<id>`).
        The processed files are stored in the specified calibration output directory.

        Args:
            verbose (bool, optional): If True, logs additional information about the
                calibration processing. Defaults to False.

        Raises:
            KeyError: If required configuration keys (e.g., "calibration" or "setup")
                are missing from the configuration file.
        """
        # Make sure a 'calibration' folder exists. We put there the output
        # calibration files.
        cal_path = Path(self.config["calibration"]["out_dir"]).resolve()
        cal_path.mkdir(exist_ok=True)

        if verbose:
            self.logger.info(
                "CALIBRATION: Get human readable calibration files."
            )

        tdc_ids = self.config["setup"]["tdc_ids"].split()
        for id in tdc_ids:
            raw_cal_file = cal_path / f"rc_{id}"
            cal_file = cal_path / f"tdc_cal_{id}"
            process_raw_cal(raw_cal_file, cal_file)

    def setup_and_calibrate(self, verbose=False) -> None:
        """Run self.setup() and self.calibrate() one after the other.
        Just for convenience.

        Args:
            verbose (bool, optional): If True, passes verbosity to the
                calibration process. Defaults to False.
        """
        self.setup(verbose=verbose)
        self.calibrate(verbose=verbose)

    def run_link_delay_measurement(self) -> None:
        """
        Prepares and runs the link delay measurement process.

        Currently, this method only logs a message indicating that the
        process is being prepared.
        """
        self.logger.info("Preparing to run the link delay measurement...")

    def ping_of_death(self) -> None:
        """
        Placeholder method for a potential reboot feature.
        See documentation here:
        https://eecloud.goip.de/dogma/doc/implementation.html#ping-of-death-pdd

        Logs a warning that the method is not implemented yet.
        """
        self.logger.warning("Method 'ping_of_death' is not implemented yet.")
