"""Unit tests for naming modules and placing imports."""

import pytest

from docgen.core.modules import ImportKind, ModuleIndex, PlacedImport, module_root

SHOP = ModuleIndex(
    ["shop", "shop.cli", "shop.orders", "shop.payments", "shop.payments.gateway"]
)


@pytest.mark.parametrize(
    ("imported", "importer", "is_package", "expected"),
    [
        ("shop.orders.Order", "shop.cli", False, "shop.orders"),
        (".orders.place_order", "shop.cli", False, "shop.orders"),
        ("..orders", "shop.payments.gateway", False, "shop.orders"),
        (".gateway", "shop.payments", True, "shop.payments.gateway"),
        # A name defined in a package's __init__ belongs to the package
        (".helper", "shop.cli", False, "shop"),
    ],
)
def test_import_of_an_analyzed_module_is_internal(
    imported, importer, is_package, expected
):
    """Absolute and relative imports both lead to the analyzed module."""
    assert SHOP.place(imported, importer, is_package) == PlacedImport(
        ImportKind.INTERNAL, expected
    )


def test_relative_import_above_the_source_root_is_not_placed():
    """from ...x reaches outside the analyzed code, so there is nothing to show."""
    assert SHOP.place("...outside", "shop.cli", False) is None


@pytest.mark.parametrize(
    ("imported", "expected"),
    [
        ("json", PlacedImport(ImportKind.STDLIB, "json")),
        ("os.path.join", PlacedImport(ImportKind.STDLIB, "os")),
        ("__future__.annotations", PlacedImport(ImportKind.STDLIB, "__future__")),
        ("requests.get", PlacedImport(ImportKind.THIRD_PARTY, "requests")),
    ],
)
def test_other_imports_are_placed_by_top_level_package(imported, expected):
    """Everything else is the standard library or a third-party package."""
    assert SHOP.place(imported, "shop.cli", False) == expected


def test_src_layout_imports_are_internal():
    """Analyzed from the project root, src/pkg is still the pkg its code imports."""
    index = ModuleIndex(["src.pkg", "src.pkg.core"])

    assert index.place("pkg.core.work", "src.pkg", True) == PlacedImport(
        ImportKind.INTERNAL, "src.pkg.core"
    )
    assert index.place("pkg", "src.pkg.core", False) == PlacedImport(
        ImportKind.INTERNAL, "src.pkg"
    )


def test_module_named_like_the_stdlib_does_not_capture_its_imports():
    """A project's utils/logging.py does not make "import logging" internal."""
    index = ModuleIndex(["app", "app.utils.logging"])

    assert index.place("logging", "app", True) == PlacedImport(
        ImportKind.STDLIB, "logging"
    )


def test_module_root_is_the_source_directory(tmp_path):
    """A plain directory is where module names start."""
    assert module_root(str(tmp_path)) == str(tmp_path)


def test_module_root_of_a_package_is_the_directory_above_it(tmp_path):
    """--source pkg/sub, inside package pkg, names modules from the directory above pkg."""
    package = tmp_path / "src" / "pkg" / "sub"
    package.mkdir(parents=True)
    for directory in (tmp_path / "src" / "pkg", package):
        (directory / "__init__.py").write_text("")

    assert module_root(str(package)) == str(tmp_path / "src")
