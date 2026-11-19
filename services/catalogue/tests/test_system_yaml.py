"""system.yaml (at the repository root) must list exactly the environment
variables this service reads in app/config.py, with the same defaults, so
the two cannot drift apart. The same file is in both services; it finds its
own entry in system.yaml from the name of its folder (services/NAME).

The format of system.yaml itself is checked in CI against system.schema.json.
"""
import re
from pathlib import Path

import yaml

SERVICE_DIR = Path(__file__).resolve().parent.parent
SERVICE_NAME = SERVICE_DIR.name
APP_DIR = SERVICE_DIR / "app"
SYSTEM_YAML = SERVICE_DIR.parent.parent / "system.yaml"

# os.environ.get("NAME", "default") or os.environ.get("NAME"), the only way
# config.py reads a setting.
ENV_READ = re.compile(r'os\.environ\.get\(\s*"([A-Z][A-Z0-9_]*)"\s*(?:,\s*"([^"]*)"\s*)?\)')

# Any read of the environment at all: os.environ.get(...), os.environ[...]
# or os.getenv(...). (Not the words "os.environ" in a comment.)
ANY_ENV_READ = re.compile(r"os\.environ\s*(?:\.get\s*\(|\[)|getenv\s*\(")


def variables_in_config():
    """{name: default as text} for every variable config.py reads."""
    text = (APP_DIR / "config.py").read_text(encoding="utf-8")
    found = dict(ENV_READ.findall(text))
    # Every read in config.py must have been matched by ENV_READ, or a
    # variable read some other way would slip past these tests.
    assert len(ANY_ENV_READ.findall(text)) == len(found)
    return found


def variables_in_system_yaml():
    """The env entries of this service in system.yaml."""
    system = yaml.safe_load(SYSTEM_YAML.read_text(encoding="utf-8"))
    return system["services"][SERVICE_NAME]["env"]


def test_system_yaml_lists_exactly_the_variables_config_reads():
    assert set(variables_in_system_yaml()) == set(variables_in_config())


def test_defaults_in_system_yaml_are_the_defaults_in_config():
    in_config = variables_in_config()
    for name, entry in variables_in_system_yaml().items():
        if entry.get("secret"):
            # A secret has no default in either place ("" means unset).
            assert in_config[name] == "", name
        else:
            assert str(entry["default"]) == in_config[name], name


def test_only_config_reads_the_environment():
    # config.py's docstring promises it lists every setting; check it.
    for path in APP_DIR.rglob("*.py"):
        if path.name != "config.py":
            assert not ANY_ENV_READ.search(path.read_text(encoding="utf-8")), path.name
