# Add to path
import sys, os

CURRENT_TEST_DIR = os.path.dirname(os.path.realpath(__file__))

sys.path.append(CURRENT_TEST_DIR + "/../src")

from data_reader import DataReader, SlayerParams
import csv
import operator
import unittest
import numpy as np

NMNIST_SIZE = 1000
NMNIST_NUM_CLASSES = 10
SKIP_TIME_CONSUMING = True # Skip tests that take a long time

def matlab_equal_to_python_event(matlab_event, python_event):
	# Cast to avoid type problems
	matlab_event = [int(e) for e in matlab_event]
	python_event = [int(e) for e in python_event]
	# Matlab is 1 indexed, Python is 0 indexed
	return ((matlab_event[0] == (python_event[0] + 1)) and (matlab_event[1] == (python_event[1] + 1)) and
		(matlab_event[2] == (python_event[2] + 1)) and (matlab_event[3] == (python_event[3])))
 
def binned_file_comparator(matlab_bin_line, python_bin_line):
	for (matlab_entry, python_entry) in zip(matlab_bin_line, python_bin_line):
		if int(matlab_entry) != int(python_entry):
			return False
	return True

# Utility function to compare ndarray to one contained in CSV file generated separately (i.e. MATLAB)
def is_array_equal_to_file(array, filepath, has_header=False, compare_function=operator.eq):
	with open(CURRENT_TEST_DIR + filepath, 'r') as csvfile:
		reader = csv.reader(csvfile)
		# Skip header
		if has_header: next(reader, None)
		for (g_truth, read_r) in zip(reader, array):
			if not compare_function(g_truth, read_r):
				return False
	return True

class TestSlayerParamsLoader(unittest.TestCase):

	def setUp(self):
		self.net_params = SlayerParams(CURRENT_TEST_DIR + "/test_files/NMNISTsmall/" + "parameters.yaml")

	# Just test one
	def test_load(self):
		self.assertEqual(self.net_params['t_end'], 350)

class TestDataReaderFolders(unittest.TestCase):

	def setUp(self):
		self.net_params = SlayerParams(CURRENT_TEST_DIR + "/test_files/NMNISTsmall/" + "parameters.yaml")

	def test_open_valid_folder(self):
		try:
			reader = DataReader(CURRENT_TEST_DIR + "/test_files/NMNISTsmall/", "train1K.txt", "test100.txt", self.net_params)
		except FileNotFoundError:
			self.fail("Valid input folder not found")

	def test_input_files_ordering(self):
		file_folder = CURRENT_TEST_DIR + "/test_files/NMNISTsmall/"
		reader = DataReader(file_folder, "train1K.txt", "test100.txt", self.net_params)
		self.assertEqual(reader.dataset_path + str(reader.training_samples[0].number) + ".bs2", file_folder + '1.bs2')

	# def test_init_invalid_network_params(self):
	# 	invalid_params = SlayerParams()
	# 	self.assertRaises(ValueError, DataReader, CURRENT_TEST_DIR + "/test_files/NMNISTsmall/", "train1K.txt", "test100.txt", invalid_params)


class TestDataReaderInputFile(unittest.TestCase):

	def setUp(self):
		self.net_params = SlayerParams(CURRENT_TEST_DIR + "/test_files/NMNISTsmall/" + "parameters.yaml")
		self.reader = DataReader(CURRENT_TEST_DIR + "/test_files/NMNISTsmall/", "train1K.txt", "test100.txt", self.net_params)
		self.minibatch_size = 12

	def test_number_of_files_valid_folder(self):
		self.assertEqual(len(self.reader.training_samples), NMNIST_SIZE)

	def test_process_event(self):
		# Actually first line of test file
		raw_bytes = bytes.fromhex('121080037d')
		# Everything is zero indexed in python, except time
		event = (19,17,2,893)
		self.assertTrue(matlab_equal_to_python_event(event, self.reader.process_event(raw_bytes)))

	# Check proper I/O
	def test_read_input_file(self):
		ev_array = self.reader.read_input_file(self.reader.training_samples[0])
		self.assertTrue(is_array_equal_to_file(ev_array, "/test_files/input_validate/1_raw_spikes.csv", has_header=True, compare_function=matlab_equal_to_python_event))

	def test_spikes_binning(self):
		ev_array = self.reader.read_input_file(self.reader.training_samples[0])
		binned_spikes = self.reader.bin_spikes(ev_array)
		self.assertTrue(is_array_equal_to_file(binned_spikes, "/test_files/input_validate/1_binned_spikes.csv", compare_function=binned_file_comparator))

	def test_high_level_binning(self):
		binned_spikes = self.reader.read_and_bin(self.reader.training_samples[0])
		self.assertTrue(is_array_equal_to_file(binned_spikes, "/test_files/input_validate/1_binned_spikes.csv", compare_function=binned_file_comparator))

	def test_loaded_label_value(self):
		self.assertEqual(self.reader.training_samples[0].label, 5)

	def test_minibatch_building(self):
		num_time_samples = int((self.net_params['t_end'] - self.net_params['t_start']) / self.net_params['t_res'])
		input_minibatch = self.reader.get_minibatch(self.minibatch_size)
		minibatch_input_size = self.net_params['input_x'] * self.net_params['input_y'] * self.net_params['input_channels']
		minibatch_length = int(self.minibatch_size * num_time_samples)
		self.assertEqual(input_minibatch.shape, (minibatch_input_size, minibatch_length))

	@unittest.skipIf(SKIP_TIME_CONSUMING == True, 'msg')
	def test_minibatch_number(self):
		# We expect 1000 / 10 minibatches before getting an error
		for i in range(int(NMNIST_SIZE / self.minibatch_size)):
			self.reader.get_minibatch(self.minibatch_size)
		self.assertRaises(IndexError, self.reader.get_minibatch, self.minibatch_size)

class TestDataReaderOutputSpikes(unittest.TestCase):

	def setUp(self):
		self.net_params = SlayerParams(CURRENT_TEST_DIR + "/test_files/NMNISTsmall/" + "parameters.yaml")
		self.reader = DataReader(CURRENT_TEST_DIR + "/test_files/training/", "train12.txt", "test12_dummy.txt", self.net_params)
		self.minibatch_size = 12

	def test_load_output_spikes(self):
		num_time_samples = int((self.net_params['t_end'] - self.net_params['t_start']) / self.net_params['t_res'])
		output_spikes = self.reader.read_output_spikes("test12_output_spikes.csv")
		self.assertEqual(output_spikes.shape, (NMNIST_NUM_CLASSES, self.minibatch_size * num_time_samples))

if __name__ == '__main__':
	unittest.main()