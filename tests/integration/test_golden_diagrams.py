"""Golden-output tests: the diagrams for a small fixture project, line for line.

The diagrams are also generated in two subprocesses with different hash
seeds, so output that depends on set ordering fails here instead of changing
from run to run. After an intended change, rewrite the expected files with
UPDATE_GOLDEN=1 and review the diff.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from docgen.core.analyzer import CodeAnalyzer
from docgen.core.diagrams import DiagramGenerator

GOLDEN_DIR = Path(__file__).parent.parent / "golden"
HASH_SEEDS = ("1", "2")
DIAGRAMS = ["architecture", "dependency"]

PROJECT = {
    "shop/__init__.py": '"""A small shop: the fixture for the golden diagrams."""\n',
    "shop/cli.py": """import argparse

from .catalog import Catalog
from .orders import place_order


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("item")
    args = parser.parse_args(argv)
    return place_order(Catalog.load(), args.item)
""",
    "shop/catalog.py": """from dataclasses import dataclass

import yaml


@dataclass
class Item:
    name: str
    price: int


class Catalog:
    def __init__(self, items):
        self.items = items

    @classmethod
    def load(cls):
        return cls(cls.parse(yaml.safe_load("[]")))

    @staticmethod
    def parse(rows):
        return [Item(**row) for row in rows]

    def find(self, name):
        return next(item for item in self.items if item.name == name)
""",
    "shop/orders.py": """import json
import logging

import requests

from .payments.gateway import charge

logger = logging.getLogger(__name__)


class Order:
    def __init__(self, item):
        self.item = item

    def total(self):
        return self.item.price


def place_order(catalog, name):
    order = Order(catalog.find(name))
    receipt = charge(order.total())
    logger.info("placed %s", json.dumps(receipt))
    requests.post("https://example.com/orders", json=receipt)
    return order
""",
    "shop/payments/__init__.py": "",
    "shop/payments/gateway.py": """import stripe

from ..catalog import Item


def charge(amount):
    return stripe.Charge.create(amount=amount)


def refund(item: Item):
    return charge(-item.price)
""",
}


def render_diagrams(root: str) -> dict[str, str]:
    """Generate the fixture project's diagrams, by name."""
    analyzer = CodeAnalyzer()
    analyses = analyzer.analyze_directory(root)
    generator = DiagramGenerator()
    return {
        "architecture": generator.generate_architecture_diagram(
            analyzer.analyze_module_imports(analyses, root=root)
        ),
        "dependency": generator.generate_dependency_diagram(
            analyzer.analyze_package_dependencies(analyses, root=root)
        ),
    }


@pytest.fixture(scope="module")
def project(tmp_path_factory) -> Path:
    """The fixture project, written to a temporary directory."""
    root = tmp_path_factory.mktemp("golden")
    for name, code in PROJECT.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code)
    return root


@pytest.fixture(scope="module")
def rendered_under_seeds(project) -> dict[str, dict[str, str]]:
    """The diagrams, generated in a fresh process under each hash seed."""
    script = (
        "import json, runpy, sys; "
        "render = runpy.run_path(sys.argv[1])['render_diagrams']; "
        "print(json.dumps(render(sys.argv[2])))"
    )
    rendered = {}
    for seed in HASH_SEEDS:
        result = subprocess.run(
            [sys.executable, "-c", script, __file__, str(project)],
            capture_output=True,
            text=True,
            check=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
        )
        rendered[seed] = json.loads(result.stdout)
    return rendered


def golden(name: str) -> str:
    """The expected diagram, as stored in tests/golden."""
    return (GOLDEN_DIR / f"{name}.mmd").read_text()


@pytest.mark.parametrize("name", DIAGRAMS)
def test_diagram_matches_golden(project, name):
    """The fixture's diagram is exactly the reviewed one."""
    diagram = render_diagrams(str(project))[name] + "\n"
    if os.environ.get("UPDATE_GOLDEN"):
        (GOLDEN_DIR / f"{name}.mmd").write_text(diagram)

    assert diagram == golden(name)


@pytest.mark.parametrize("seed", HASH_SEEDS)
@pytest.mark.parametrize("name", DIAGRAMS)
def test_diagram_is_the_same_under_every_hash_seed(rendered_under_seeds, name, seed):
    """Set and dict ordering does not change the output."""
    assert rendered_under_seeds[seed][name] + "\n" == golden(name)
