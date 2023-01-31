import serial.tools.list_ports
import serial.tools.list_ports_common
from serial import Serial
import platform

from .tmcl_board import TMCLBoard


def port_name(port: serial.tools.list_ports_common.ListPortInfo) -> str:
    """Takes a port object and returns the string name that can be used to open it as a serial connection."""
    if platform.system() == "Windows":
        port_name = port.name
    elif platform.system() == "Linux":
        port_name = "/dev/" + port.name
    else:
        raise Exception
    return port_name

def get_trinamics() -> "dict[int:TMCLBoard]":
    """Return a dictionary of Trinamic board serial addresses and associated objects."""
    boards = {}

    ports = serial.tools.list_ports.comports()

    for p in ports:
        if "VID:PID=2A3C:0100" in p.hwid or "VID:PID=16D0:0653" in p.hwid: # If it is a Trinamic TMCM-1110/3110/6110 Board
            board = TMCLBoard(port_name(p)) # Create board object
            address = board.get_param("Serial Address") # Get Address

            boards[address] = board

    return boards
