from typing import Any, List, Tuple

from serial import Serial
import struct
import json
import importlib.resources
import threading
import weakref
import time

from .exceptions import *
from .tmcl_motion import TMCLMotion
from .tmcl_gpio import TMCLGPIO



with importlib.resources.open_text("automationlib.trinamic", "TMCLCommands.json") as commandsFile:
    _DATA = json.load(commandsFile)


COMMANDS = _DATA["Commands"]
PARAMETERS = _DATA["Parameters"]
ERRORS = _DATA["Errors"]



MESSAGE_STRUCTURE=">BBBBiB" #byte,byte,byte,byte,integer,byte
REPLY_STRUCTURE=">BBBBiB" #byte,byte,byte,byte,integer,byte


# Fairly certain the occaisional weird error where it returns a status code of 0 are due to the system not being thread-safe.
# Adding a threading lock on writing to test.

class TMCLBoard():
    """Class to handle interaction with the trinamic control boards."""

    def __init__(self, portName):
        self.serial_port = Serial(portName, timeout=0.2)
        self.serial_lock = threading.Lock()

        self.close = weakref.finalize(self, self._close, self.serial_port)

    @staticmethod
    def _close(serial_port:Serial):
        serial_port.close()
    
    @property
    def is_closed(self):
        return not self.close.alive
    
    def assert_open(self):
        if self.is_closed():
            raise ObjectClosedException()
    
    def get_motion(self, axis: int, config:"dict[str:Any] | str") -> TMCLMotion:
        """Get a motion object corresponding to a specified axis of the board."""
        self.assert_open()
        return TMCLMotion(self, axis, config)
    
    def get_gpio(self):
        """Get the gpio object for the gpio pins on the board."""
        self.assert_open()
        return TMCLGPIO(self)
    
    def set_param(self, parameter:"int | str", value:int):
        """Set global parameter."""
        self.assert_open()
        self.command("Set Global", parameter, 0, value)
    def get_param(self, parameter:"int | str") -> int:
        """Get global parameter."""
        self.assert_open()
        return self.command("Get Global", parameter, 0, 0)

    def set_coordinate(self, coordinate_number:int, axis:TMCLMotion, position:float):
        """Set the value of the coordinate for the specified axis."""
        self.assert_open()
        self.command("Set Coordinate", coordinate_number, axis.axis_number, round(axis.units_to_steps(position)))
    def get_coordinate(self, coordinate_number:int, axis:TMCLMotion):
        """Get the value of the coordinate for the specified axis"""
        self.assert_open()
        return axis.steps_to_units(self.command("Get Coordinate", coordinate_number, axis.axis_number, 0))
    
    def move_coordinate(self, coordinate_number:int, axes:List[TMCLMotion]):
        """Move multiple axes together to the coordinate specified. Behaves strangely for axes with low acceleration."""
        self.assert_open()
        if len(axes) > 3:
            raise MultiAxisException(f"Move coordinate can only move 3 axes with interpolation. {len(axes)} were specified.")
        
        axis_bitmask = 0b01000000 # 6th bit specifies move together
        for axis in axes:
            if not axis.parent_board is self:
                raise MultiAxisException(f"Axis {axis} is not connected to this control board.")
            axis_bitmask = axis_bitmask | (1 << axis.axis_number) # Set the bit corresponding to the axis number of the axes

        self.command("Move", "Coordinate", axis_bitmask, coordinate_number)
    
    def move_absolute(self, positions:List[Tuple[TMCLMotion, float]], coordinate_number:int=1):
        """Move the specified axes to the specified positions."""
        self.assert_open()
        if len(positions) > 3:
            raise MultiAxisException(f"Move coordinate can only move 3 axes with interpolation. {len(positions)} were specified.")
        
        for position in positions:
            self.set_coordinate(coordinate_number, position[0], position[1])
        self.move_coordinate(coordinate_number, [position[0] for position in positions])
    
    def command(self, command:"int | str", type_:"int | str", bank:int, value:int) -> int:
        """Write the specified command to the Trinamic board and return the board's response."""
        self.assert_open()

        def calc_checksum(message_without_checksum:struct) -> int:
            """Calculate the checksum of the message"""
            checksum = 0
            for i in message_without_checksum:
                checksum += int(i)

            # Gets the least significant byte
            checksum = checksum & 255
            return checksum

        # Moved these functions inside since they should NEVER be called by themselves.
        def write(self, command:int, type_:int, bank:int, value:int):
            # To calculate checksum, format message without checksum
            checksum = calc_checksum(struct.pack(MESSAGE_STRUCTURE[:-1], 1, command, type_, bank, value))

            # Create and send message
            message = struct.pack(MESSAGE_STRUCTURE, 1, command, type_, bank, value, checksum)
            self.serial_port.write(message)
        
        def reply(self) -> int:
            replyBytes = self.serial_port.read(9)
            if len(replyBytes) < 9:
                raise TMCLBadResponse("Board timed out! Check connection.")
            reply = struct.unpack(REPLY_STRUCTURE,replyBytes)

            status_code = reply[2]
            value = reply[4]

            # Raise exception if it doesn't give a happy reply
            if status_code not in (100, 101):
                try:
                    error_message = ERRORS[str(status_code)]
                except:
                    error_message = f"Unknown error code: {status_code}"

                raise TMCLBadResponse(error_message)
            else:
                return value
        

        with self.serial_lock:
            # If the command or type are strings, try looking them up in the json file.
            if type(command) == int:
                command_num = command
            else:
                command_num = COMMANDS[command]

            if type(type_) == int:
                type_num = type_
            else:
                type_num = PARAMETERS[type_]

            write(self, command_num, type_num, bank, value)
            return reply(self)
    
    def reset_serial(self):
        """Used to reset the serial connection in the case that something went wrong (eg. a thread was aborted while sending a command.)."""
        self.serial_port.reset_output_buffer()
        time.sleep(0.002) # Give the trinamic board a moment to make sure everything's processed.
        self.serial_port.reset_input_buffer()

        # Release the lock if it's stuck.
        if self.serial_lock.locked():
            self.serial_lock.release()
        
