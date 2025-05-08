"""Utility functions used across the BlackCat project."""

import logging
import socket
import subprocess
import threading
from importlib.resources import files
from pathlib import Path


def get_default_config_path() -> Path:
    """Retrieve the path to the default config file included in the package."""
    return files("blackcat").joinpath("config.cfg")


def run_shell_script(
    script_path: str,
    arguments: list[str] | None = None,
    logger: logging.Logger | None = None,
    process_name: str = "",
) -> None:
    """Run a shell script and logs its output in real-time.

    Arguments
    ---------
    - script_path : str
        Path to the script to execute.
    - arguments : list, optional
        List of command-line arguments to pass.
    - logger : logging.Logger, optional
        Logger instance to log messages.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    if process_name == "":
        process_name = "PROCESS"

    # Ensure arguments is always a list
    if arguments is None:
        arguments = []
    elif isinstance(arguments, str):
        # Convert string to list (safe for space-separated args)
        arguments = arguments.split()

    # Construct command
    cmd = [script_path] + arguments

    logger.debug(f"{process_name}: Running script: {' '.join(cmd)}")

    try:
        # Start subprocess
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        # Log stdout in real-time
        for line in process.stdout:
            logger.debug(f"{process_name}: {line.strip()}")

        # Log stderr in real-time
        for line in process.stderr:
            logger.error(f"{process_name} ERROR: {line.strip()}")

        # Ensure process completes
        process.wait()

        # If script fails, raise an exception
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, script_path)

    except subprocess.CalledProcessError as e:
        logger.error(
            f"{process_name} ERROR: Script '{script_path}' "
            f"failed with error code {e.returncode}."
        )
        raise  # Re-raise for higher-level handling

    except Exception as e:
        logger.error(
            f"{process_name} ERROR: Unexpected error in script "
            f"'{script_path}': {e}"
        )
        raise  # Re-raise unexpected errors


class UDPListener:
    """UDP Listener helper class to receive and log UDP packets.

    This class sets up a UDP socket to listen for incoming packets on a
    specified port. The received data is written to a specified output
    file, and logging is used to track the activity and any errors.

    Attributes
    ----------
    - port : int
        The port number to listen on.
    - out_file : str
        The path to the file where received data will be written.
    - process_name : str
        A name to identify the process in log messages.
    - logger : logging.Logger
        Logger instance to log messages.
    - stop_event : threading.Event
        Event used to signal the listener to stop.
    - thread : threading.Thread
        The thread running the listener.
    - sock : socket.socket
        The UDP socket used for listening.
    """

    def __init__(
        self,
        port: int,
        out_file: str,
        logger: logging.Logger | None = None,
        process_name: str = "UDP_LISTENER",
    ):
        """Initialize the UDPListener instance.

        Parameters
        ----------
        - port : int
            The port number to listen on.
        - out_file : str
            The path to the file where received data will be written.
        - logger : logging.Logger, optional
            A logger instance to log messages. If not provided, a default
            logger is used.
        - process_name : str, optional
            A name to identify the process in log messages. Defaults to
            "UDP_LISTENER".
        """
        self.port = port
        self.out_file = out_file
        self.process_name = process_name
        self.logger = logger or logging.getLogger(__name__)
        self.ready_event = threading.Event()  # To signal readiness.
        self.stop_event = threading.Event()  # To stop the listener.
        self.thread = None  # Thread that will run the listener.
        self.sock = None  # UDP socket for listening.

    def start(self):
        """Start the UDP listener in a background thread.

        This method creates a UDP socket, binds it to the specified port,
        and starts a thread to listen for incoming packets. The received
        data is written to the specified output file.
        """
        # Make sure the ready_event is clear before starting
        self.ready_event.clear()

        def listen():
            # Create a UDP socket
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Bind the socket to the address and port.
            # "0.0.0.0" means that we listen for any packet that shows up
            # on port `self.port`, no matter where it is from.
            self.sock.bind(("0.0.0.0", self.port))
            self.sock.settimeout(2.0)  # Periodic check for stop_event - 2s.

            self.logger.info(
                f"{self.process_name}: Listening on port {self.port}, "
                f"writing to {self.out_file}"
            )

            # Signal that the listener is ready
            self.ready_event.set()

            # Open the output file in binary write mode
            with open(self.out_file, "wb") as f:
                while not self.stop_event.is_set():
                    try:
                        # Receive data from the socket
                        data, _ = self.sock.recvfrom(4096)
                        f.write(data)
                    except TimeoutError:
                        # Timeout occurred, check if we should stop
                        # because of the stop_event.
                        continue
                    except Exception as e:
                        self.logger.error(f"{self.process_name}: Error: {e}")
                        break

            # Close the socket when done
            self.sock.close()
            self.logger.info(
                f"{self.process_name}: Listener on port {self.port} closed."
            )

        self.thread = threading.Thread(target=listen, daemon=True)
        self.thread.start()

    def stop(self):
        """Stop the UDP listener.

        Signals the listener to stop and waits for the thread to terminate.
        """
        self.logger.info(
            f"{self.process_name}: Stopping listener on port {self.port}..."
        )
        self.stop_event.set()  # Signal the listener to stop.
        if self.thread:
            # Wait for the thread to terminate.
            self.logger.debug(
                f"{self.process_name}: Waiting for listener thread to "
                "terminate..."
            )
            self.thread.join(timeout=2)


class USBReader:
    """USB Reader helper class to read data from a USB device and save it to a file.

    This class sets up a background thread to read data from a USB device
    and write it to a specified output file.

    Attributes
    ----------
    - device : str
        The path to the USB device (e.g., '/dev/ttyUSB0').
    - out_file : str
        The path to the file where received data will be written.
    - process_name : str
        A name to identify the process in log messages.
    - logger : logging.Logger
        Logger instance to log messages.
    - stop_event : threading.Event
        Event used to signal the reader to stop.
    - thread : threading.Thread
        The thread running the reader.
    """

    def __init__(
        self,
        device: str,
        out_file: str,
        logger: logging.Logger | None = None,
        process_name: str = "USB_READER",
    ):
        """
        Initialize the USBReader instance.

        Parameters
        ----------
        - device : str
            The path to the USB device (e.g., '/dev/ttyUSB0').
        - out_file : str
            The path to the file where received data will be written.
        - logger : logging.Logger, optional
            A logger instance to log messages. If not provided, a default
            logger is used.
        - process_name : str, optional
            A name to identify the process in log messages. Defaults to
            "USB_READER".
        """
        self.device = device
        self.out_file = out_file
        self.process_name = process_name
        self.logger = logger or logging.getLogger(__name__)
        self.stop_event = threading.Event()  # To stop the reader.
        self.thread = None  # Thread that will run the reader.

    def start(self):
        """Start the USB reader in a background thread."""
        self.logger.info(
            f"{self.process_name}: Starting USB reader for device {self.device}, "
            f"writing to {self.out_file}"
        )

        def read_usb():
            try:
                with open(self.out_file, "wb") as file:
                    self.logger.debug(
                        f"{self.process_name}: Reading from {self.device} and "
                        f"saving to {self.out_file}..."
                    )
                    # Use subprocess to read from the USB device
                    process = subprocess.Popen(
                        ["cat", self.device],
                        stdout=file,
                        stderr=subprocess.PIPE,
                    )
                    while not self.stop_event.is_set():
                        # Poll the process to check if it's still running
                        if process.poll() is not None:
                            break
                    # Terminate the process if stop_event is set
                    if self.stop_event.is_set():
                        process.terminate()
                        self.logger.info(
                            f"{self.process_name}: USB reading stopped."
                        )
            except FileNotFoundError as e:
                self.logger.error(f"{self.process_name}: Error: {e}")
            except Exception as e:
                self.logger.error(f"{self.process_name}: Unexpected error: {e}")

        # Start the USB reading in a background thread
        self.thread = threading.Thread(target=read_usb, daemon=True)
        self.thread.start()
        self.logger.info(
            f"{self.process_name}: USB reader started in the background."
        )

    def stop(self):
        """Stop the USB reader.

        Signals the reader to stop and waits for the thread to terminate.
        """
        self.logger.info(
            f"{self.process_name}: Stopping USB reader for device {self.device}..."
        )
        self.stop_event.set()  # Signal the reader to stop.
        if self.thread:
            # Wait for the thread to terminate.
            self.logger.debug(
                f"{self.process_name}: Waiting for USB reader thread to terminate..."
            )
            self.thread.join(timeout=2)
        self.logger.info(f"{self.process_name}: USB reader stopped.")
