"""Bootstrap fail-closed compartido por toda la suite.

Debe cargarse antes que los módulos de aplicación. Mantiene incluso el valor de
respaldo de ``database.DB`` lejos de ``pechy.db`` entre setUp y tearDown.
"""

from ._bootstrap import TEST_DB
