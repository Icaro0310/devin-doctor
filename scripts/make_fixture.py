"""Generate a fixture data dir for manual CLI verification (not shipped)."""
import sys
from pathlib import Path

from devin_internals.fixtures import create_devin_data_dir

root = Path(sys.argv[1])
create_devin_data_dir(root)
(root / "credentials.toml").write_text('[auth]\ntoken = "x"\n')
print(root)
