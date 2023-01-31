from __future__ import annotations

from typing import Any
import json


from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .tmcl_board import TMCLBoard
from .exceptions import ObjectClosedException

class TMCLMotion:
    """
        Factory class for TrinamicMotion.
        The details of initialization and conversion can vary between boards.
        The subclass used is specified by the "Motion Type" parameter in the trinamic section of the json file.
    """

    def __new__(cls, parent_board: TMCLBoard, axis_number:int, config:"dict[str:Any] | str"):
        if isinstance(config, str):
            # Open JSON config if specified
            with open(config) as config_file:
                config = json.load(config_file)
        else:
            # Assuming config is a dict
            config = config

        try:
            motion_type = config["Trinamic"]["Motion Type"]
        except KeyError:
            motion_type = None

        if motion_type == "External Driver":
            return super().__new__(TrinamicExternal)
        else:
            return super().__new__(TrinamicDefault)

    def __init__(self, parent_board: TMCLBoard, axis_number:int, config:"dict[str:Any] | str"):
        # Reference can be used for coordinating movements and to ensure board object isn't deleted before gpio and motors are done.
        self.parent_board: TMCLBoard = parent_board
        self.axis_number = axis_number

        # Load config file if specified
        if type(config) == str:
            # Open JSON config if specified
            with open(config) as config_file:
                self.config = json.load(config_file)
        else:
            # Assuming config is a dict
            self.config = config

        if "Left Limit Switch Disable" not in self.config["Trinamic"]:
            self.set_param("Left Limit Switch Disable", 0)
        if "Right Limit Switch Disable" not in self.config["Trinamic"]:
            self.set_param("Right Limit Switch Disable", 0)
        if "Reference Search Coarse Speed" not in self.config["Trinamic"]:
            self.set_param("Reference Search Coarse Speed", self.get_param("Maximum Speed"))
        if "Reference Search Coarse Speed" not in self.config["Trinamic"]:
            self.set_param("Reference Search Fine Speed", 10)

        # Initialize based on config file
        for key, value in self.config["Trinamic"].items():
            if key != "Motion Type":
                self.set_param(key, value)

        # Initialize General config. Must be after Trinamic section because of things like divisors and microstep settings.
        super().__init__(self.config["General"])

    def assert_parent_open(self):
        if self.parent_board.is_closed:
            raise ObjectClosedException()

    # Axis Parameters
    def set_param(self, parameter:str, value:int):
        """Set the value of the specified register."""
        self.assert_parent_open()
        self.parent_board.command("Set Axis", parameter, self.axis_number, value)

    def get_param(self, parameter:str) -> int:
        """Return the value of the specified register."""
        self.assert_parent_open()
        return self.parent_board.command("Get Axis", parameter, self.axis_number, 0)

    # Movement
    def move_relative(self, distance:float):
        """Move motor a relative distance."""
        self.assert_parent_open()
        self.move_steps_relative(round(self.units_to_steps(distance)))

    def move_absolute(self, position:float):
        """Move motor to an absolute position based on current 0 position."""
        self.assert_parent_open()
        self.move_steps_absolute(round(self.units_to_steps(position)))

    def move_velocity(self, velocity:float):
        """Move indefinitely at the specified velocity."""
        self.assert_parent_open()
        self.move_vinternal_velocity(round(self.vpps_to_vint(self.units_to_steps(velocity))))

    def move_steps_relative(self, steps:int):
        """Move motor a specific number of steps."""
        self.assert_parent_open()
        self.parent_board.command("Move", "Relative", self.axis_number, steps)

    def move_steps_absolute(self, steps:int):
        """Move motor to an absolute position based on current 0 position."""
        self.assert_parent_open()
        self.parent_board.command("Move", "Absolute", self.axis_number, steps)

    def move_vinternal_velocity(self, velocity:int):
        self.assert_parent_open()
        if(velocity < 0):
            self.parent_board.command("Rotate Left", 0, self.axis_number, abs(velocity))
        else:
            self.parent_board.command("Rotate Right", 0, self.axis_number, velocity)

    def stop(self):
        """Stop the motor."""
        self.assert_parent_open()
        self.parent_board.command("Stop", 0, self.axis_number, 0)

    def home(self, to_right=False):
        """Home the motor. If to_right is true, it will home to the positive direction. Else, it will home to the negative direction."""
        self.assert_parent_open()
        self.set_param("Reference Search Mode", 65 if to_right else 1)
        self.parent_board.command("Reference Search", "Start", self.axis_number, 0)

    ##Getting position
    def get_position(self) -> float:
        """Get position of motor."""
        self.assert_parent_open()
        return self.steps_to_units(self.get_steps())

    def get_steps(self) -> int:
        """Get position of motor in steps"""
        self.assert_parent_open()
        return self.get_param("Actual Position")

    def set_speed(self, speed:float):
        """Set the speed of the stage."""
        self.assert_parent_open()
        self.set_param("Maximum Speed", self.convert_speed(speed))
    
    def get_speed(self) -> float:
        self.assert_parent_open()
        return self.steps_to_units(self.vint_to_vpps(self.get_param("Maximum Speed")))

    def set_acceleration(self, acceleration:float):
        """Set the acceleration of the stage."""
        self.assert_parent_open()
        self.set_param("Maximum Acceleration", self.convert_acceleration(acceleration))
    
    def get_acceleration(self) -> float:
        self.assert_parent_open()
        return self.steps_to_units(self.aint_to_apps(self.get_param("Maximum Acceleration")))

    ##Getting State
    def is_moving(self) -> bool:
        """
        Return if motor is moving. This works regardless of whether the motor is in position mode, velocity mode, or a reference search.

        Important: since this gets the current velocity of the motor, this will return False for a millisecond or two after starting a movement.
        Use a short delay first if waiting for the motor to arrive somewhere.

        The main other candidate we have used in the past is the position reached flag, but that doesn't go on if the motor hits a limit switch.
        The target velocity behaves similarly. If you have any suggestions, please message Gideon Rabson in slack.
        """
        self.assert_parent_open()
        return self.get_param("Actual Speed") != 0
    
    def is_homing(self) -> bool:
        """Return if the motor is homing."""
        self.assert_parent_open()
        return self.parent_board.command("Reference Search", "Status", self.axis_number, 0) != 0

    # Steps and units
    def units_to_steps(self, value:float) -> float:
        """Convert a value from stage units to steps."""
        raise NotImplementedError

    def steps_to_units(self, steps:float) -> float:
        """Convert a value from steps to stage units."""
        raise NotImplementedError

    # Internal units
    # Equations from firmware manual chapter 6.1
    def vint_to_vpps(self, Vint:float) -> float:
        self.assert_parent_open()
        return float(Vint) * (16 * (10**6)) / ((2**self.get_param("Pulse Divisor")) * 2048 * 32)

    def vpps_to_vint(self, Vpps:float) -> float:
        """Convert velocity from steps per second to internal units. Must be converted to int in [0..2047] before use."""
        self.assert_parent_open()
        return float(Vpps) * ((2**self.get_param("Pulse Divisor")) * 2048 * 32) / (16 * (10**6))

    def aint_to_apps(self, Aint:float) -> float:
        """Convert a value from steps to stage units."""
        self.assert_parent_open()
        return float(Aint) * ( (16 * (10**6)) ** 2) / (2 ** (self.get_param("Ramp Divisor") + self.get_param("Pulse Divisor") + 29))

    def apps_to_aint(self, Apps:float) -> float:
        """Convert acceleration from steps per second^2 to internal units. Must be converted to int in [0..2047] before use."""
        self.assert_parent_open()
        return float(Apps) * (2 ** (self.get_param("Ramp Divisor") + self.get_param("Pulse Divisor") + 29)) / ( (16 * (10**6)) ** 2)

    # Overflow prevention
    def convert_speed(self, speed:float) -> int:
        self.assert_parent_open()
        return max(1, min(round(self.vpps_to_vint(self.units_to_steps(speed))), 2047))

    def convert_acceleration(self, acceleration:float) -> int:
        self.assert_parent_open()
        return max(1, min(round(self.apps_to_aint(self.units_to_steps(acceleration))), 2047))
    
    def disable(self):
        raise NotImplementedError
    
    def enable(self):
        raise NotImplementedError

class TrinamicDefault(TMCLMotion):
    def __init__(self, parent_board: TMCLBoard, axis_number: int, config: "dict[str:Any] | str"):
        super().__init__(parent_board, axis_number, config)
        if "Chopper Off Time" not in self.config["Trinamic"]:
            self.config["Trinamic"]["Chopper Off Time"] = 5     # Seems to be the default, no reason to mess with it
        self.enable()

    def disable(self):
        """Cut power to motor. It is unclear whether current level 0 is actually 0 current, but I hope so."""
        self.assert_parent_open()
        self.set_param("Chopper Off Time", 0)
    
    def enable(self):
        """Only needed after disabling. Motor is automatically enabled on initialization."""
        self.assert_parent_open()
        self.set_param("Chopper Off Time", self.config["Trinamic"]["Chopper Off Time"])

    def units_to_steps(self, value:float) -> float:
        """Convert a value from stage units to steps."""
        self.assert_parent_open()
        return float(value) * (2**self.get_param("Microstep Resolution")) / self.config["General"]["distance per step"]

    def steps_to_units(self, steps:float) -> float:
        """Convert a value from steps to stage units."""
        self.assert_parent_open()
        return float(steps) / (2**self.get_param("Microstep Resolution")) * self.config["General"]["distance per step"]

class TrinamicExternal(TMCLMotion):
    def units_to_steps(self, value:float) -> float:
        """Convert a value from stage units to steps."""
        self.assert_parent_open()
        return float(value) / self.config["General"]["distance per step"]

    def steps_to_units(self, steps:float) -> float:
        """Convert a value from steps to stage units."""
        self.assert_parent_open()
        return float(steps) * self.config["General"]["distance per step"]