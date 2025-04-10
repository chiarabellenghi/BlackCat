import time
import subprocess
from pathlib import Path
from blackcat.base_objects import BaseTDC
from blackcat.utils import run_shell_script, UDPListener, USBReader
from blackcat.decoders import process_raw_cal


class BlackCat(BaseTDC):
    """This class is hopefully helpful to use the BlackCat system.
    With methods implemented for this object, you can setup the
    system, run calibration measurements, run round-trip link delay
    measurements.
    """

    def __init__(self, config_file, sub_dir=None, logging_level="INFO"):
        super().__init__(config_file, sub_dir, logging_level)

        self.listeners = None

    def setup(self, verbose=False) -> None:
        """Sets up everything, assigning IDs and broadcast bits
        to all modules.

        Raises:
            KeyError: If the "setup" section or "script" key is missing in
                the config file.
        """
        self.logger.info("SETUP: Starting the setup process...")

        # Read the script name from the config file
        script_name = self.config["setup"]["script"]

        # Construct the full path to the script using the dynamically located scripts_dir
        script = self.scripts_dir / script_name

        arguments = ["--config_file", str(self.config_file)]
        if verbose:
            arguments = ["--verbose"]

        run_shell_script(
            script.as_posix(),
            arguments=arguments,
            logger=self.logger,
            process_name="SETUP",
        )
        self.logger.info("SETUP: DONE.")

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
        self.logger.info("CALIBRATION: Starting the calibration process...")

        # Read the script name from the config file
        script_name = self.config["calibration"]["script"]

        # Construct the full path to the script using the dynamically located scripts_dir
        script = self.scripts_dir / script_name

        arguments = [
            "--config_file",
            str(self.config_file),
            "--save_path",
            str(self.save_path),
        ]
        if verbose:
            arguments.append("--verbose")

        run_shell_script(
            script.as_posix(),
            arguments=arguments,
            logger=self.logger,
            process_name="CALIBRATION",
        )

        # Process the raw calibration files
        self.logger.debug("CALIBRATION: Processing raw calibration files...")
        self.process_raw_calibration(verbose=verbose)
        self.logger.info("CALIBRATION: DONE.")

    def process_raw_calibration(self, verbose=False) -> None:
        """
        Processes raw calibration files and generates human-readable
        calibration files.

        This method ensures that the output directory for calibration files
        exists, retrieves the list of TDC IDs from the configuration, and
        processes each raw calibration file (`rc_<id>`) into a human-readable
        format (`tdc_cal_<id>`). The processed files are stored in the
        specified calibration output directory.

        Args:
            verbose (bool, optional): If True, logs additional information
                about the calibration processing. Defaults to False.

        Raises:
            KeyError: If required configuration keys (e.g., "calibration" or
            "setup") are missing from the configuration file.
        """
        # Make sure a 'calibration' folder exists. We put there the output
        # calibration files.
        cal_path = self.save_path / self.config["calibration"]["out_dir"]
        cal_path.mkdir(exist_ok=True)
        self.logger.debug(
            f"CALIBRATION: Created calibration directory: {cal_path}"
        )

        if verbose:
            self.logger.debug(
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
        # To make sure everything is ok, we setup again after calibration.
        self.setup(verbose=verbose)

    def start_udp_listeners(self, outfile_suffix=None) -> None:
        """Starts the UDP listeners for the specified ports.

        This method reads the port configuration from the config file and
        starts a UDP listener for each port. The listeners are stored in
        the `self.listeners` dictionary.

        Raises:
            KeyError: If the "run" section or "ports" key is missing in
                the config file.
        """
        self.logger.debug("UDP LISTENER: Starting UDP listeners...")

        # Read port configuration from the config file
        ports = self.config["run"]["ports"].split()
        tdcs = self.config["setup"]["tdc_ids"].split()

        self.listeners = {}
        for port, tdc in zip(ports, tdcs):
            # Assign an automatic filename if none is provided
            if outfile_suffix is None:
                out_file = self.save_path / f"data_{tdc}.bin"
            else:
                out_file = self.save_path / f"data_{tdc}_{outfile_suffix}.bin"

            # Start UDP listeners
            listener = UDPListener(
                port=int(port),
                out_file=out_file,
                logger=self.logger,
                process_name="UDP LISTENER",
            )
            listener.start()
            # Wait for the socket to be confirmed running
            listener.ready_event.wait()
            self.listeners[port] = listener

            time.sleep(1)

    def run_link_delay_measurement(
        self, outfile_suffix=None, verbose=False
    ) -> None:
        """
        Prepares and runs the link delay measurement process.

        Currently, this method only logs a message indicating that the
        process is being prepared.
        """

        if verbose:
            self.logger.info(
                "DELAY LINK MEASUREMENT: Starting the link delay measurement"
            )
        if not self.listeners:
            self.logger.info(
                "DELAY LINK MEASUREMENT: No UDP listeners found. "
                "Starting UDP listeners..."
            )
            # Start the UDP listeners
            self.start_udp_listeners(outfile_suffix=outfile_suffix)

        if verbose:
            self.logger.debug(
                "DELAY LINK MEASUREMENT: Link delay measurement is ready. "
                "Starting measurement..."
            )

        # Read the script name from the config file
        script_name = self.config["run"]["script_start"]

        # Construct the full path to the script using the dynamically located scripts_dir
        script = self.scripts_dir / script_name

        run_shell_script(
            script.as_posix(),
            logger=self.logger,
            process_name="DELAY LINK MEASUREMENT",
        )

        self.logger.info("DELAY LINK MEASUREMENT: Running...")

    def stop_measurement(self) -> None:
        """
        Placeholder method for stopping the measurement.
        Currently, this method does not perform any actions.
        """
        self.logger.debug("STOP MEASUREMENT: Stopping all UDP listeners...")

        # Stop the BC system
        # Read the script name from the config file
        script_name = self.config["run"]["script_stop"]

        # Construct the full path to the script using the dynamically located scripts_dir
        script = self.scripts_dir / script_name

        run_shell_script(
            script.as_posix(),
            logger=self.logger,
            process_name="STOP MEASUREMENT",
        )

        if self.listeners:
            for listener in self.listeners.values():
                listener.stop()
        else:
            self.logger.debug("STOP MEASUREMENT: No UDP listeners to stop.")

    def reboot(self, max_retry=2, verbose=False) -> None:
        """
        Placeholder method for a potential reboot feature.
        See documentation here:
        https://eecloud.goip.de/dogma/doc/implementation.html#ping-of-death-pdd

        Logs a warning that the method is not implemented yet.
        """
        self.logger.info("REBOOT: Broadcasting ping of death...")

        # Number of modules I expect to be online after the reboot.
        expected_count = len(self.config["setup"]["tomcat_ids"].split()) + len(
            self.config["setup"]["tdc_ids"].split()
        )

        # Send ping of death... not super safe.
        # Read the script name from the config file
        script_name = self.config["run"]["script_reboot"]

        # Construct the full path to the script using the dynamically located scripts_dir
        script = self.scripts_dir / script_name

        def ping_of_death():
            run_shell_script(
                script.as_posix(),
                logger=self.logger,
                process_name="REBOOT",
            )
            # Wait a bit for the system to recover
            self.logger.debug(
                "REBOOT: Waiting for the system to recover from the ping of death..."
            )
            time.sleep(5)

            self.logger.info(
                "REBOOT: System has been rebooted. Waiting for all modules to "
                "come back online..."
            )

            count = 0
            modules_online = self.check_modules_online(
                expected_count=expected_count
            )
            while not modules_online and count < 10:  # hard-coded... not nice.
                count += 1
                self.logger.debug(
                    "REBOOT: Waiting for all modules to come back online..."
                )
                time.sleep(2)
                modules_online = self.check_modules_online(
                    expected_count=expected_count
                )

            return modules_online

        attempts = 0
        while attempts < max_retry:
            attempts += 1
            self.logger.debug(f"REBOOT: Attempt {attempts} of {max_retry}...")
            # Broadcast the ping of death
            success = ping_of_death()

            if success:
                self.logger.info("REBOOT: All modules are back online.")
                self.logger.info("REBOOT: Reboot successful.")
                break  # Exit the loop if reboot is successful
            else:
                self.logger.error(
                    "REBOOT: Not all modules are back online. Rebooting once "
                    "more..."
                )
        else:
            self.logger.error(
                f"REBOOT: Not all modules are back online after {max_retry} "
                "attempts. Please check the system."
            )
            raise RuntimeError(
                f"REBOOT: Not all modules are back online after {max_retry} "
                "attempts."
            )

        # Re-run setup after reboot
        self.setup(verbose=verbose)

    def check_modules_online(self, expected_count, verbose=False) -> bool:
        """
        Checks if all expected modules are back online after a reboot.

        Returns
        -------
        - bool
            True if all expected modules are online, False otherwise.

        Raises
        ------
        - RuntimeError
            If the `dog discover` command fails.
        """
        self.logger.info(
            "DOG DISCOVER: Checking if all modules are back online..."
        )

        try:
            # Run the `dog discover` command
            result = subprocess.run(
                ["dog", "discover"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            output = result.stdout
            if verbose:
                self.logger.debug(f"DOG DISCOVER: output:\n{output}")

            # Parse the output to count the number of modules
            lines = output.strip().split("\n")
            module_lines = [
                line
                for line in lines
                if line.strip()
                and not line.startswith("---")
                and not line.startswith("IP-ADDR")
            ]

            # Check if the number of modules matches the expected count
            if len(module_lines) == expected_count:
                self.logger.info(
                    f"DOG DISCOVER: All {expected_count} modules back online."
                )
                return True
            else:
                self.logger.warning(
                    f"DOG DISCOVER: Expected {expected_count} modules, "
                    f"but found {len(module_lines)}."
                )
                return False

        except subprocess.CalledProcessError as e:
            self.logger.error(
                f"DOG DISCOVER: Failed to run 'dog discover': {e.stderr}. "
                f"Command: {e.cmd}"
            )
            raise RuntimeError(f"DOG DISCOVER: command failed: {e.stderr}")


class USBTDC(BaseTDC):
    """
    A class to interact with an external TDC device.
    """

    def __init__(self, config_file, device, sub_dir=None, logging_level="INFO"):
        super().__init__(config_file, sub_dir, logging_level)

        self.device = Path(device).as_posix()
        self.name = Path(device).name
        self.logger.info(f"{self.device}: Initialized.")

    def setup(self, verbose=False) -> None:
        """Sets up everything, assigning IDs and broadcast bits
        to all modules.

        Raises:
            KeyError: If the "setup" section or "script" key is missing in
                the config file.
        """
        self.logger.info(f"{self.name} SETUP: Starting the setup process...")

        # Read the script name from the config file
        script_name = self.config["external_TDCs"]["script_setup"]

        # Construct the full path to the script using the dynamically located scripts_dir
        script = self.scripts_dir / script_name

        arguments = ["--ext_device", self.device]
        if verbose:
            arguments.append("--verbose")

        run_shell_script(
            script.as_posix(),
            arguments=arguments,
            logger=self.logger,
            process_name=f"{self.name} SETUP",
        )
        self.logger.info(f"{self.name} SETUP: DONE.")

    def start_usb_reading(self, outfile_suffix=None) -> None:
        """
        Starts reading data from the USB device in the background.

        Args:
            outfile_suffix (str): Suffix for the output file where data will be saved.
        """
        if outfile_suffix is None:
            out_file = self.save_path / f"data_{self.name}.bin"
        else:
            out_file = self.save_path / f"data_{self.name}_{outfile_suffix}.bin"

        self.logger.info(
            f"{self.name} READ: Starting USB reading to {out_file}..."
        )
        self.usb_reader = USBReader(
            device=self.device,
            out_file=str(out_file),
            logger=self.logger,
            process_name=f"{self.name} USB_READER",
        )
        self.usb_reader.start()

    def stop_usb_reading(self) -> None:
        """
        Stops the USB reading process.
        """
        if self.usb_reader:
            self.logger.info(f"{self.name} READ: Stopping USB reading...")
            self.usb_reader.stop()
            self.usb_reader = None
        else:
            self.logger.warning(
                f"{self.device} READ: No USB reading process to stop."
            )
