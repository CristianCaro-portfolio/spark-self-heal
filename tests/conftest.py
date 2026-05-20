"""
Pytest fixtures for spark-self-heal tests.

Provides a SparkSession shared across tests in the same module
(scope='module' is a good trade-off between speed and isolation).

JAVA_HOME resolution:
  PySpark needs a JDK to launch the JVM gateway. We resolve JAVA_HOME
  in this order:
    1. an existing JAVA_HOME environment variable (CI / user override)
    2. the macOS Homebrew openjdk@17 path
    3. /usr/libexec/java_home (system fallback on macOS)
  This makes the tests runnable from a plain `pytest` invocation,
  without requiring the user to remember to export JAVA_HOME first.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest


def _resolve_java_home() -> str | None:
    if os.environ.get("JAVA_HOME"):
        return os.environ["JAVA_HOME"]

    brew_jdk = Path("/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home")
    if brew_jdk.is_dir():
        return str(brew_jdk)

    helper = shutil.which("/usr/libexec/java_home")
    if helper:
        try:
            out = subprocess.check_output([helper, "-v", "17"], stderr=subprocess.DEVNULL)
            return out.decode().strip() or None
        except subprocess.CalledProcessError:
            pass

    return None


_java_home = _resolve_java_home()
if _java_home:
    os.environ["JAVA_HOME"] = _java_home
    os.environ["PATH"] = f"{_java_home}/bin:" + os.environ.get("PATH", "")

from pyspark.sql import SparkSession  # noqa: E402  (must come after JAVA_HOME)


@pytest.fixture(scope="module")
def spark() -> SparkSession:
    """A local SparkSession suitable for unit tests."""
    return (
        SparkSession.builder
        .appName("spark-self-heal-tests")
        .master("local[2]")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.ui.enabled", "false")
        # AWS Glue (Spark 3.x) defaults ansi to false. PySpark 4.x defaults
        # it to true, which makes to_timestamp raise on malformed input
        # instead of returning NULL. We pin it off so local tests mirror
        # the production runtime semantics.
        .config("spark.sql.ansi.enabled", "false")
        .getOrCreate()
    )
