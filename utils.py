import subprocess
import logging
from typing import List, Optional


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
    - arguments : list | None
        List of command-line arguments to pass.
    - logger : logging.Logger | None
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

    logger.info(f"{process_name}: Running script: {' '.join(cmd)}")

    try:
        # Start subprocess
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        # Log stdout in real-time
        for line in process.stdout:
            logger.info(f"{process_name}: {line.strip()}")

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
