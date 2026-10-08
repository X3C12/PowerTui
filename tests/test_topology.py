import os
import shutil
import tempfile
import unittest
from powertui.sys_controller import SystemController

class TestSystemControllerTopology(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        # Mock 4 logical CPUs: 2 sharing Core 0 (P-core) and 2 standalone single-thread Cores 1 and 2 (E-cores)
        # cpu0 (core 0)
        os.makedirs(os.path.join(self.test_dir, "cpu0", "topology"))
        with open(os.path.join(self.test_dir, "cpu0", "topology", "core_id"), "w") as f:
            f.write("0\n")
        # cpu0 never has an 'online' file in kernel
        
        # cpu1 (core 0 thread 2 - hyperthreading -> makes Core 0 a P-core)
        os.makedirs(os.path.join(self.test_dir, "cpu1", "topology"))
        with open(os.path.join(self.test_dir, "cpu1", "topology", "core_id"), "w") as f:
            f.write("0\n")
        with open(os.path.join(self.test_dir, "cpu1", "online"), "w") as f:
            f.write("1\n")

        # cpu2 (core 1 - single thread -> E-core)
        os.makedirs(os.path.join(self.test_dir, "cpu2", "topology"))
        with open(os.path.join(self.test_dir, "cpu2", "topology", "core_id"), "w") as f:
            f.write("1\n")
        with open(os.path.join(self.test_dir, "cpu2", "online"), "w") as f:
            f.write("1\n")

        # cpu3 (core 2 - single thread -> E-core)
        os.makedirs(os.path.join(self.test_dir, "cpu3", "topology"))
        with open(os.path.join(self.test_dir, "cpu3", "topology", "core_id"), "w") as f:
            f.write("2\n")
        with open(os.path.join(self.test_dir, "cpu3", "online"), "w") as f:
            f.write("0\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_core_discovery_and_classification(self):
        controller = SystemController(sys_cpu_dir=self.test_dir)
        self.assertEqual(len(controller.p_cores), 1, "Should detect 1 P-core")
        self.assertEqual(len(controller.e_cores), 2, "Should detect 2 E-cores")
        
        # Check logical CPU grouping
        self.assertEqual(controller.p_cores[0].logical_cpus, [0, 1])
        self.assertEqual(controller.e_cores[0].logical_cpus, [2])
        self.assertEqual(controller.e_cores[1].logical_cpus, [3])
        
        # Check online status logic
        self.assertTrue(controller.p_cores[0].is_online, "Core 0 is online because CPU0 is boot core")
        self.assertTrue(controller.e_cores[0].is_online, "Core 1 should be online")
        self.assertFalse(controller.e_cores[1].is_online, "Core 2 should be offline")
        
        online_p, online_e = controller.get_online_counts()
        self.assertEqual((online_p, online_e), (1, 1))


class TestSystemControllerFrequencyHeuristic(unittest.TestCase):
    """Single-threaded cores above 4 GHz are treated as P-cores."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self._add_cpu(0, core_id=0, max_freq=5000000)  # > 4 GHz -> P
        self._add_cpu(1, core_id=1, max_freq=3000000)  # <= 4 GHz -> E

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _add_cpu(self, cpu, core_id, max_freq):
        topo = os.path.join(self.test_dir, f"cpu{cpu}", "topology")
        os.makedirs(topo)
        with open(os.path.join(topo, "core_id"), "w") as handle:
            handle.write(f"{core_id}\n")
        if max_freq is not None:
            cpufreq = os.path.join(self.test_dir, f"cpu{cpu}", "cpufreq")
            os.makedirs(cpufreq)
            with open(os.path.join(cpufreq, "cpuinfo_max_freq"), "w") as handle:
                handle.write(f"{max_freq}\n")

    def test_single_thread_high_freq_core_is_p_core(self):
        controller = SystemController(sys_cpu_dir=self.test_dir)
        self.assertEqual(len(controller.p_cores), 1)
        self.assertEqual(controller.p_cores[0].logical_cpus, [0])
        self.assertEqual(len(controller.e_cores), 1)
        self.assertEqual(controller.e_cores[0].logical_cpus, [1])

    def test_topology_is_cached_after_first_refresh(self):
        controller = SystemController(sys_cpu_dir=self.test_dir)
        p_first = list(controller.p_cores)
        e_first = list(controller.e_cores)
        controller.refresh_topology()
        self.assertEqual(controller.p_cores, p_first)
        self.assertEqual(controller.e_cores, e_first)


if __name__ == "__main__":
    unittest.main()
