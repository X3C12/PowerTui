import os
import tempfile
import unittest

import powertui.platform_detect as pd


class TestOsReleaseParsing(unittest.TestCase):
    def test_parse_os_release_handles_quotes_and_comments(self):
        text = (
            "# comment\n"
            'NAME="Kali GNU/Linux"\n'
            "VERSION_ID=2026.3\n"
            "ID=kali\n"
            "ID_LIKE=debian\n"
            "\n"
            "EMPTY=\n"
        )
        data = pd.parse_os_release(text)
        self.assertEqual(data["NAME"], "Kali GNU/Linux")
        self.assertEqual(data["VERSION_ID"], "2026.3")
        self.assertEqual(data["ID"], "kali")
        self.assertEqual(data["ID_LIKE"], "debian")

    def test_classify_family_by_id_and_id_like(self):
        self.assertEqual(pd.classify_family("kali", ["debian"]), "debian")
        self.assertEqual(pd.classify_family("ubuntu", []), "debian")
        self.assertEqual(pd.classify_family("arch", []), "arch")
        self.assertEqual(pd.classify_family("rocky", ["rhel", "fedora"]), "rhel")
        self.assertEqual(pd.classify_family("weirdos", []), "other")

    def test_classify_family_id_like_only_when_id_unknown(self):
        # No direct match on the ID: the ID_LIKE chain must decide the family.
        self.assertEqual(pd.classify_family("steamos", ["arch"]), "arch")
        self.assertEqual(pd.classify_family("weirdos", ["rhel", "fedora"]), "rhel")
        self.assertEqual(pd.classify_family("weirdos", ["ubuntu"]), "debian")
        self.assertEqual(pd.classify_family("weirdos", ["unknown", "opensuse"]), "suse")
        self.assertEqual(pd.classify_family("weirdos", ["nope", "alsonope"]), "other")

    def test_classify_family_direct_id_is_case_insensitive(self):
        # classify_family() normalizes raw input, so direct callers are safe.
        self.assertEqual(pd.classify_family("Kali", ["Debian"]), "debian")
        self.assertEqual(pd.classify_family("kali", ["debian"]), "debian")

    def test_parse_os_release_handles_weird_quoting(self):
        text = (
            "PRETTY=\"has = sign\"\n"
            "NAME='Single Quoted Name'\n"
            "ID_LIKE=\"debian   ubuntu\"\n"
            "TRAILING=\"foo\"   \n"
            "MISMATCHED=\"unbalanced'\n"
            "BARE=value\n"
        )
        data = pd.parse_os_release(text)
        # partition on the first "=" keeps embedded equals signs intact.
        self.assertEqual(data["PRETTY"], "has = sign")
        self.assertEqual(data["NAME"], "Single Quoted Name")
        self.assertEqual(data["ID_LIKE"], "debian   ubuntu")
        self.assertEqual(data["TRAILING"], "foo")
        # A mismatched quote is preserved verbatim rather than half-stripped.
        self.assertEqual(data["MISMATCHED"], "\"unbalanced'")
        self.assertEqual(data["BARE"], "value")

    def test_parse_os_release_tolerates_junk_lines(self):
        text = "not-a-kv-line\n# comment\n\n NOEQUAL \nKEY=  spaced  \n"
        data = pd.parse_os_release(text)
        self.assertEqual(data, {"KEY": "spaced"})

    def test_read_os_release_missing_returns_empty(self):
        self.assertEqual(pd.read_os_release(["/does/not/exist/os-release"]), {})

    def test_read_os_release_skips_empty_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = os.path.join(tmp, "empty")
            with open(empty, "w") as handle:
                handle.write("# only a comment\n")
            second = os.path.join(tmp, "second")
            with open(second, "w") as handle:
                handle.write("ID=second\n")
            self.assertEqual(pd.read_os_release([empty, second]), {"ID": "second"})


class TestDetectionHelpers(unittest.TestCase):
    def test_detect_package_manager_prefers_first_found(self):
        fake = {"dnf": "/usr/bin/dnf"}
        self.assertEqual(pd.detect_package_manager(which=lambda c: fake.get(c)), "dnf")

    def test_detect_package_manager_unknown(self):
        self.assertEqual(pd.detect_package_manager(which=lambda c: None), "unknown")

    def test_detect_privilege_tool(self):
        fake = {"doas": "/usr/bin/doas"}
        self.assertEqual(pd.detect_privilege_tool(which=lambda c: fake.get(c)), "doas")

    def test_detect_init_system(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write("systemd\n")
            path = handle.name
        try:
            self.assertEqual(pd.detect_init_system(proc_comm_path=path), "systemd")
        finally:
            os.unlink(path)

    def test_detect_init_system_blank_file_is_unknown(self):
        # An existing-but-blank comm file must not fall through to the real
        # /proc/1/comm fallback (detect_init_system breaks on empty content).
        with tempfile.NamedTemporaryFile("w", delete=False) as handle:
            handle.write("   \n")
            path = handle.name
        try:
            self.assertEqual(pd.detect_init_system(proc_comm_path=path), "unknown")
        finally:
            os.unlink(path)

    def test_detect_privilege_tool_prefers_sudo(self):
        fake = {"sudo": "/usr/bin/sudo", "doas": "/usr/bin/doas"}
        self.assertEqual(pd.detect_privilege_tool(which=lambda c: fake.get(c)), "sudo")

    def test_detect_privilege_tool_none(self):
        self.assertEqual(pd.detect_privilege_tool(which=lambda c: None), "none")

    def test_detect_package_manager_order_apt_before_dnf(self):
        fake = {"apt": "/usr/bin/apt", "dnf": "/usr/bin/dnf"}
        self.assertEqual(pd.detect_package_manager(which=lambda c: fake.get(c)), "apt")


class TestDetectDistro(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.os_release = os.path.join(self.tmp, "os-release")
        with open(self.os_release, "w") as handle:
            handle.write(
                'NAME="Test Distro"\nID=testdistro\nID_LIKE="debian ubuntu"\nVERSION_ID=1.2\n'
            )
        self.comm = os.path.join(self.tmp, "comm")
        with open(self.comm, "w") as handle:
            handle.write("openrc\n")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp)

    def test_detect_distro_fields(self):
        info = pd.detect_distro(
            os_release_paths=[self.os_release],
            which=lambda c: "/usr/bin/apt" if c == "apt" else None,
            proc_comm_path=self.comm,
        )
        self.assertEqual(info.id, "testdistro")
        self.assertEqual(info.name, "Test Distro")
        self.assertEqual(info.version, "1.2")
        self.assertEqual(info.id_like, ["debian", "ubuntu"])
        self.assertEqual(info.family, "debian")
        self.assertEqual(info.package_manager, "apt")
        self.assertEqual(info.init_system, "openrc")
        self.assertEqual(info.display, "Test Distro 1.2")

    def test_detect_distro_missing_file_is_graceful(self):
        info = pd.detect_distro(
            os_release_paths=[os.path.join(self.tmp, "does-not-exist")],
            which=lambda c: None,
            proc_comm_path=self.comm,
        )
        self.assertEqual(info.id, "unknown")
        self.assertEqual(info.family, "other")
        self.assertEqual(info.name, "Unknown Linux")
        self.assertEqual(info.version, "")
        self.assertEqual(info.id_like, [])

    def _write_release(self, body):
        path = os.path.join(self.tmp, "release-%d" % len(os.listdir(self.tmp)))
        with open(path, "w") as handle:
            handle.write(body)
        return path

    def test_detect_distro_id_like_only_decides_family(self):
        path = self._write_release('NAME="Arch-ish"\nID=steamos\nID_LIKE="arch"\n')
        info = pd.detect_distro(
            os_release_paths=[path],
            which=lambda c: None,
            proc_comm_path=self.comm,
        )
        self.assertEqual(info.id, "steamos")
        self.assertEqual(info.family, "arch")
        self.assertEqual(info.id_like, ["arch"])

    def test_detect_distro_normalizes_id_and_id_like_case(self):
        path = self._write_release('NAME="Kali"\nID=KALI\nID_LIKE="Debian Ubuntu"\n')
        info = pd.detect_distro(
            os_release_paths=[path],
            which=lambda c: None,
            proc_comm_path=self.comm,
        )
        self.assertEqual(info.id, "kali")
        self.assertEqual(info.id_like, ["debian", "ubuntu"])
        self.assertEqual(info.family, "debian")

    def test_detect_distro_weird_quoting_and_embedded_equals(self):
        path = self._write_release(
            "NAME='Single Quoted Name'\n"
            'VERSION="1 = 2"\n'
            "ID=weird\n"
            "ID_LIKE='rhel fedora'\n"
        )
        info = pd.detect_distro(
            os_release_paths=[path],
            which=lambda c: None,
            proc_comm_path=self.comm,
        )
        self.assertEqual(info.name, "Single Quoted Name")
        self.assertEqual(info.version, "1 = 2")
        self.assertEqual(info.family, "rhel")
        self.assertEqual(info.display, "Single Quoted Name 1 = 2")

    def test_detect_distro_falls_back_to_version_key(self):
        path = self._write_release('NAME="NoIdVersion"\nID=whatever\nVERSION=99\n')
        info = pd.detect_distro(
            os_release_paths=[path],
            which=lambda c: None,
            proc_comm_path=self.comm,
        )
        self.assertEqual(info.version, "99")
        self.assertEqual(info.display, "NoIdVersion 99")


if __name__ == "__main__":
    unittest.main()
