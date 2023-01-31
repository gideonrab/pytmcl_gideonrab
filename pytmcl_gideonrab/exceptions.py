
class TMCLException(Exception):
    pass

class ObjectClosedException(TMCLException):
    pass

class TMCLBadResponse(TMCLException):
    pass
class MultiAxisException(TMCLException):
    pass

class GPIOException(TMCLException):
    pass
class PinException(GPIOException, ValueError):
    pass