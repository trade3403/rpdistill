import io
import unittest
from rpdistill.rust_parity import CASES,MAX_OUTPUT,read_exact

class RustParityTests(unittest.TestCase):
    def test_fixed_budget_and_masks(self):
        self.assertEqual(len(CASES),2)
        self.assertEqual(MAX_OUTPUT,(7*512+12*65001)*4+40)
        self.assertTrue(CASES[1][3][0])
        self.assertFalse(CASES[1][1][-1])
    def test_truncated_stream(self):
        self.assertEqual(read_exact(io.BytesIO(b"abc"),3),b"abc")
        with self.assertRaises(ValueError):
            read_exact(io.BytesIO(b"abc"),4)
