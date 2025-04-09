import subprocess
import logging
from typing import List, Optional
import socket
import threading


def run_shell_script(
    script_path: str,
    arguments: Optional[List[str]] = None,
    logger: Optional[logging.Logger] = None,
    process_name: str = "",
) -> None:
    """Runs a shell script and logs its output in real-time.

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
        logger: Optional[logging.Logger] = None,
        process_name: str = "UDP_LISTENER",
    ):
        """
        Initializes the UDPListener instance.

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
                    except socket.timeout:
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
        """
        Stops the UDP listener.
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
