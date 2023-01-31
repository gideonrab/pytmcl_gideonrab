import os
import sys
import inspect

# act as if in package instead of in test folder outside
currentdir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parentdir = os.path.dirname(currentdir)
sys.path.insert(0, parentdir)


from io import TextIOWrapper
import weakref

from automationlib.utility import assert_open

class DestructorExample:
    def __init__(self, name:str, file:str):
        self.name = name
        print(f"{self.name} initialized!")
        self.file = open(file)


        self.close = weakref.finalize(self, self._close, self.name, self.file)

    @staticmethod
    def _close(name:str, file:TextIOWrapper):
        print(f"{name} destroyed!")
        file.close()
    
    @property
    def is_closed(self):
        return not self.close.alive

    def read(self):
        assert_open(self)
        return self.file.readline()



# Implicit destruction
foo = DestructorExample("foo", "readme.md")
print(foo.name + " says: " + foo.read(), end="")
    # Will get destroyed at program exit


# Explicit Destruction
bar = DestructorExample("bar", "pyproject.toml")
print(bar.name + " says: " + bar.read(), end="")
bar.close()
try:
    print(bar.read(), end="") # Raises a ValueError now that it is closed
except:
    print("ValueError raised.")
bar.close() # Close second time just to prove no error


# Context Manager
from contextlib import closing

with closing(DestructorExample("baz", "LICENSE")) as baz:
    print(baz.name + " says: " + baz.read(), end="")