import unittest
import os
import sys

# Add the parent directory to sys.path so we can import calculator
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from calculator import calculate

class TestCalculator(unittest.TestCase):
    def test_addition(self):
        self.assertEqual(calculate("2 + 2"), 4)

    def test_subtraction(self):
        self.assertEqual(calculate("5 - 3"), 2)
        
    def test_vulnerability(self):
        """
        Proof of concept (PoC) for the eval() vulnerability.
        It attempts to execute an OS command to create a file.
        The test asserts that this file should NOT be created (if patched).
        Thus, the test will fail if the code is vulnerable.
        """
        test_file = "hacked.txt"
        if os.path.exists(test_file):
            os.remove(test_file)
            
        payload = "__import__('os').system('touch hacked.txt')"
        
        # Execute payload
        calculate(payload)
        
        is_vulnerable = os.path.exists(test_file)
        
        # Clean up
        if is_vulnerable:
            os.remove(test_file)
            
        self.assertFalse(is_vulnerable, "Vulnerability detected: OS command execution was successful.")

if __name__ == '__main__':
    unittest.main()
