"""
Provides a utility function to configure logging for the application.

It ensures consistent logging behavior across all components.
"""

import logging
import sys


def configure_logging(
    level=logging.INFO, log_to_file=False, filename="blackcat.log"
):
    """Configure the logging system.

    Ensures consistent logging across all classes.
    """
    # Check if logging is already configured
    if logging.getLogger().hasHandlers():
        return

    # Always log to stdout (Notebook output)
    handlers = [logging.StreamHandler(sys.stdout)]

    if log_to_file:
        # Append logs to file
        handlers.append(logging.FileHandler(filename, mode="a"))

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    )
