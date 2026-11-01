"""The shared foundations of small self-hosted web apps.

Each module is imported on its own (``jigkit.settings``, ``jigkit.db``, ...); importing the
package pulls in nothing beyond the version.
"""

from importlib.metadata import version

__version__ = version("jigkit")
