import configparser
import logging
from pathlib import Path
from importlib.resources import files
from blackcat.logger import configure_logging


class BaseTDC:
    """
    A base class for shared functionality between TDC devices.
    """

    def __init__(
        self,
        config_file: str,
        sub_dir: str = None,
        logging_level: str = "INFO",
    ) -> None:
        """Initializes the object giving it a base directory where
        we are going to work and a config file.

        Args:
            config_file (str): Path to the configuration file.
            subdir (str, optional): Subdirectory for saving data. This is
                appended to the save path defined in the config file.
                It can be useful when running multiple measurements
                requiring a calibration each. Defaults to None.
            logging_level (int, optional): Logging level. Defaults to
                INFO.

        Raises:
            FileNotFoundError: If the base directory does not exist or is
                not a directory.
        """
        # Initialize logger for this class
        if logging_level == "INFO":
            logging_level = logging.INFO
        elif logging_level == "DEBUG":
            logging_level = logging.DEBUG
        else:
            raise ValueError(
                f"Invalid logging level: {logging_level}. Use 'INFO', 'DEBUG'."
            )
        configure_logging(level=logging_level)
        self.logger = logging.getLogger(self.__class__.__name__)

        # Locate the scripts directory within the package
        self.scripts_dir = files("blackcat.scripts")
        self.logger.debug(
            f"INIT: Located scripts directory: {self.scripts_dir}"
        )

        # Read the config file
        self.config = configparser.ConfigParser()
        self.config_file = Path(config_file).resolve()
        if not self.config_file.exists():
            raise FileNotFoundError(
                f"INIT ERROR: Configuration file '{self.config_file}' "
                "does not exist."
            )
        self.config.read(self.config_file)
        self.save_path = Path(self.config["save"]["path"]).resolve()
        if sub_dir:
            self.save_path /= sub_dir
        if not self.save_path.exists():
            self.save_path.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"INIT: Created save directory: {self.save_path}")
        else:
            self.logger.debug(
                f"INIT: Save directory already exists: {self.save_path}"
            )

        self.logger.debug(
            f"INIT: Loaded configuration from: {self.config_file}"
        )

    def setup(self) -> None:
        """
        Sets up the TDC system by running the setup script defined in the
        configuration file.
        """
        pass
