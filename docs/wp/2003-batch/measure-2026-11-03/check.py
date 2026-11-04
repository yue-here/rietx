import rietx, platform, sys
from rietx.model import compiled
print(rietx.__file__, rietx.__version__, platform.platform(), platform.machine(), sys.version.split()[0])
print(compiled.set_enabled(True))
import inspect
print(compiled.set_enabled(True))
