import sys
from pathlib import Path
from types import ModuleType

package_name = Path(__file__).parents[1].name
addon_name = f"{package_name}.addon"
sys.modules.setdefault(addon_name, ModuleType(addon_name))
