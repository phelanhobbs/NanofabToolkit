import unittest
from src.peakCount import count_peaks

class TestPeakCount(unittest.TestCase):

    def test_count_peaks_valid_data(self):
        # Test with a valid data file
        peak_count, pressure_times, pressures, peaks = count_peaks('tests/test_data.txt', height=0.5)
        self.assertEqual(peak_count, expected_peak_count)  # Replace with expected count
        self.assertIsNotNone(pressure_times)
        self.assertIsNotNone(pressures)
        self.assertIsNotNone(peaks)

    def test_count_peaks_no_data(self):
        # Test with a file that has no valid data
        peak_count, pressure_times, pressures, peaks = count_peaks('tests/empty_data.txt')
        self.assertEqual(peak_count, 0)
        self.assertIsNone(pressure_times)
        self.assertIsNone(pressures)
        self.assertIsNone(peaks)

    def test_count_peaks_invalid_file(self):
        # Test with an invalid file path
        peak_count, pressure_times, pressures, peaks = count_peaks('tests/non_existent_file.txt')
        self.assertEqual(peak_count, 0)
        self.assertIsNone(pressure_times)
        self.assertIsNone(pressures)
        self.assertIsNone(peaks)

    def test_count_peaks_with_prominence(self):
        # Test with prominence parameter
        peak_count, pressure_times, pressures, peaks = count_peaks('tests/test_data.txt', prominence=0.1)
        self.assertEqual(peak_count, expected_peak_count_with_prominence)  # Replace with expected count

if __name__ == '__main__':
    unittest.main()