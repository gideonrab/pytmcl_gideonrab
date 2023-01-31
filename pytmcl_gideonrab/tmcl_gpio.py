from typing import TYPE_CHECKING, Tuple
if TYPE_CHECKING:
    from .tmcl_board import TMCLBoard

from .exceptions import PinException, ObjectClosedException

# Pin names:
# Use either an int = (10*bank number) + pin number
# eg. bank 0 pin 4 = 4, bank 2 pin 1 = 21
# Or str of the form in the tmcm manual (IN_3, OUT_7, AIN_1, etc.)


class TMCLGPIO:
    
    def __init__(self, parent_board: TMCLBoard):
        # Reference can be used for coordinating movements and to ensure board object isn't deleted before gpio and motors are done.
        self.parent_board = parent_board
    
    def assert_parent_open(self):
        if self.parent_board.is_closed:
            raise ObjectClosedException()

    def pin_lookup(self, pin:"int | str") -> Tuple[int, int]:
        """Returns bank, pin_number."""
        self.assert_parent_open()
        if isinstance(pin, int):
            bank_num = pin // 10
            pin_num = pin % 10
            if bank_num not in (0, 1, 2):
                raise PinException(f"{pin} is not in bank 0, 1 or 2.")

        elif isinstance(pin, str):
            split_str = pin.split("_")
            if len(split_str) != 2:
                raise PinException(f"{pin} does not contain exactly one underscore.")
            bank_str = split_str[0]
            pin_str = split_str[1]

            try:
                pin_num = int(pin_str)
            except ValueError:
                raise PinException(f"{pin} does not end in valid base 10 number.")

            if bank_str in ("IN", "AIN"):
                bank_num = 0
            elif bank_str == "OUT":
                bank_num = 2
            else:
                raise PinException(f"{pin} does not begin with AIN, IN, or OUT")
        
        else:
            raise ValueError(f"{pin} is not an int or a str.")
            
        
        return bank_num, pin_num


    def digital_write(self, pin:"int | str", value:bool):
        """Set the specified pin to the specified value."""
        self.assert_parent_open()
        bank_num, pin_num = self.pin_lookup(pin)
        if bank_num != 2:
            raise PinException(f"{pin} is an input pin.")
        self.parent_board.command("Set IO", pin_num, 2, int(bool(value))) # Output pins are bank 2
    
    def digital_read(self, pin:int) -> bool:
        """Get the value of the specified digital pin."""
        self.assert_parent_open()
        bank_num, pin_num = self.pin_lookup(pin)
        return bool(self.parent_board.command("Get IO", pin_num, bank_num, 0)) # Digital output is on bank 2
    
    def analog_read(self, pin:int) -> int:
        """Get the value of the specified analog pin."""
        self.assert_parent_open()
        bank_num, pin_num = self.pin_lookup(pin)
        if bank_num == 0 and pin_num not in (0, 4): # Digital input pin
            raise PinException(f"{pin} is a digital input pin.")
        elif bank_num == 2:
            raise PinException(f"{pin} is a digital output pin.")
        return self.parent_board.command("Get IO", pin_num, 1, 0) # Analog input is bank 1