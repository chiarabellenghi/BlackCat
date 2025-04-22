import configparser
import logging
from pathlib import Path
from importlib.resources import files
from blackcat.logger import configure_logging
from blackcat.utils import get_default_config_path


class BaseDevice:
    """
    A base class for external devices.

    This class provides common attributes (e.g., configuration file, save path, logging)
    and enforces the presence of a `setup()` method in derived classes.
    """

    DEFAULT_SAVE_PATH = "./data"

    def __init__(
        self,
        config_file: str = None,
        save_path: str = None,
        logging_level: str = "INFO",
    ) -> None:
        """
        Initializes the object, providing a configuration file and a save path.

        Args:
            config_file (str, optional): Path to the configuration file.
                If None, uses the default configuration file.
            save_path (str, optional): Directory for saving data. Defaults to
                None.
            logging_level (str, optional): Logging level. Defaults to 'INFO'.

        Raises:
            FileNotFoundError: If the configuration file does not exist.
            ValueError: If an invalid logging level is provided.
        """
        # Initialize logger for this class
        if not hasattr(logging, logging_level.upper()):
            raise ValueError(
                f"Invalid logging level: {logging_level}. Use 'INFO', 'DEBUG', etc."
            )
        logging_level = getattr(logging, logging_level.upper())
        configure_logging(level=logging_level)
        self.logger = logging.getLogger(self.__class__.__name__)

        # Locate the scripts directory within the package
        try:
            self.scripts_dir = files("blackcat.scripts")
            self.logger.debug(
                f"INIT: Located scripts directory: {self.scripts_dir}"
            )
        except ModuleNotFoundError as e:
            self.logger.error(f"INIT: Failed to locate 'blackcat.scripts': {e}")
            raise RuntimeError("'blackcat.scripts' package not found.")

        # Use the default config file if none is provided
        if config_file is None:
            self.config_file = get_default_config_path()
            self.logger.debug("INIT: Using default configuration file.")
        else:
            self.config_file = Path(config_file).resolve()
            self.logger.debug(
                "INIT: Using user-provided configuration file: "
                f"{self.config_file}"
            )

        # Read the config file
        self.config = configparser.ConfigParser()
        if not self.config_file.exists():
            self.logger.error(
                f"INIT: Configuration file '{self.config_file}' does not exist."
            )
            raise FileNotFoundError(
                f"Configuration file '{self.config_file}' does not exist."
            )
        self.config.read(self.config_file)
        self.logger.debug(
            f"INIT: Loaded configuration from: {self.config_file}"
        )

        # Check if a save_path was specified. Otherwise fall back to default.
        self._save_path: Path = Path(
            save_path or self.DEFAULT_SAVE_PATH
        ).resolve()
        if not self.save_path.exists():
            self.save_path.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"INIT: Created save directory: {self.save_path}")
        else:
            self.logger.warning(
                f"INIT: Save directory already exists: {self.save_path}. "
                "You might be overwriting files!"
            )

    @property
    def save_path(self) -> Path:
        """Getter for the `save_path` attribute."""
        return self._save_path

    @save_path.setter
    def save_path(self, new_path: str) -> None:
        """Setter for the `save_path` attribute."""
        new_path = Path(new_path).expanduser()
        try:
            new_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise ValueError(f"Failed to create save path '{new_path}': {e}")
        self._save_path = new_path
        self.logger.info(f"Save path updated to: {self._save_path}")

    def setup(self) -> None:
        """
        Sets up the TDC system by running the setup script defined in the
        configuration file.
        """
        pass
