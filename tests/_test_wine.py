import os
import tempfile
from unittest import TestCase
from unittest.mock import MagicMock, patch

from lutris.runners import wine
from lutris.runners.commands import wine as wine_commands
from lutris.util.test_config import setup_test_environment
from lutris.util.wine import wine as wine_utils

setup_test_environment()


class TestDllOverrides(TestCase):
    def test_env_format(self):
        overrides = {
            "d3dcompiler_43": "native,builtin",
            "d3dcompiler_47": "native,builtin",
            "dnsapi": " builtin",
            "dwrite": " disabled",
            "winemenubuilder": "disabled",
            "rasapi32": " native",
        }
        env_string = wine.get_overrides_env(overrides)
        self.assertEqual(env_string, "d3dcompiler_43,d3dcompiler_47=n,b;dnsapi=b;rasapi32=n;dwrite,winemenubuilder=")


class TestWineArchitecture(TestCase):
    @staticmethod
    def create_prefix(architecture):
        prefix = tempfile.TemporaryDirectory()
        with open(os.path.join(prefix.name, "system.reg"), "w", encoding="utf-8") as registry:
            registry.write("WINE REGISTRY Version 2\n#arch=%s\n" % architecture)
        return prefix

    def test_existing_prefix_takes_precedence_over_wine_executable(self):
        prefix = self.create_prefix("win32")
        self.addCleanup(prefix.cleanup)

        with patch.object(wine_utils.system, "path_exists", return_value=True):
            self.assertEqual(wine.detect_arch(prefix.name, "/opt/wine/bin/wine"), "win32")

    def test_existing_64_bit_prefix_is_detected_on_32_bit_host(self):
        prefix = self.create_prefix("win64")
        self.addCleanup(prefix.cleanup)

        with (
            patch.object(wine_utils, "WINE_DEFAULT_ARCH", "win32"),
            patch.object(wine_utils.system, "path_exists", return_value=False),
        ):
            self.assertEqual(wine.detect_arch(prefix.name, "/opt/wine/bin/wine"), "win64")

    def test_missing_prefix_uses_64_bit_host_default_for_modern_wine(self):
        with (
            patch.object(wine_utils, "WINE_DEFAULT_ARCH", "win64"),
            patch.object(wine_utils.system, "path_exists", return_value=False),
        ):
            self.assertEqual(wine.detect_arch("/missing/prefix", "/opt/wine/bin/wine"), "win64")

    def test_missing_prefix_uses_32_bit_host_default(self):
        with (
            patch.object(wine_utils, "WINE_DEFAULT_ARCH", "win32"),
            patch.object(wine_utils.system, "path_exists", return_value=False),
        ):
            self.assertEqual(wine.detect_arch("/missing/prefix", "/opt/wine/bin/wine"), "win32")

    def test_wine64_executable_is_detected_for_new_prefix(self):
        with (
            patch.object(wine_utils, "WINE_DEFAULT_ARCH", "win32"),
            patch.object(wine_utils.proton, "is_proton_path", return_value=False),
            patch.object(wine_utils.system, "path_exists", return_value=True),
        ):
            self.assertEqual(wine.detect_arch("/missing/prefix", "/opt/wine/bin/wine"), "win64")

    def test_wineexec_passes_existing_prefix_architecture_to_wine(self):
        prefix = self.create_prefix("win32")
        self.addCleanup(prefix.cleanup)

        runner = MagicMock()
        runner.system_config = {"disable_runtime": True}
        runner.get_env.return_value = {}

        with (
            patch.object(wine_commands.proton, "is_proton_path", return_value=False),
            patch.object(wine_commands, "get_real_executable", return_value=("winecfg", [], None)),
            patch.object(wine_commands, "use_lutris_runtime", return_value=False),
            patch.object(wine_commands.system, "execute", return_value="") as execute,
        ):
            wine_commands.wineexec(
                "winecfg",
                prefix=prefix.name,
                wine_path="/opt/wine/bin/wine",
                runner=runner,
                blocking=True,
            )

        self.assertEqual(execute.call_args.kwargs["env"]["WINEARCH"], "win32")
