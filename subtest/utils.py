# -*- coding: utf-8 -*-
"""
Some utils functions.
"""
from __future__ import print_function

import argparse
import datetime
import shutil
import sys
from itertools import product
from pathlib import Path
from shutil import copyfile

import tensorflow as tf
from loguru import logger
from ruamel.yaml import YAML

from . import constants


def load_cfg(yaml_filepath):
    """
    Load a YAML configuration file.

    Args:
        yaml_filepath : str

    Returns:
        cfg : dict
    """
    logger.info("Loading experiment yaml file")

    yaml = YAML(typ='safe')
    with open(yaml_filepath, "r") as stream:
        # This will fail if there are duplicated keys in the YAML file
        cfg = yaml.load(stream)
    logger.info(cfg)
    return cfg


def get_scenario_params_list(config):
    """
    Create parameter list for each scenario from the config.

    Parameters
    ----------
    config : dict
        Dictionary of parameters for experiment

    Returns
    -------
    scenario_params_list : list
        list of parameters for each scenario.

    """

    scenario_params_list = []
    # Separate scenarios from different dataset
    config_dataset = []

    for list_scenario in config:
        if isinstance(list_scenario['dataset_name'], dict):
            for dataset_name in list_scenario['dataset_name'].keys():
                # Add path to init model from an existing model
                dataset_scenario = list_scenario.copy()
                dataset_scenario['dataset_name'] = [dataset_name]
                if list_scenario['dataset_name'][dataset_name] is None:
                    dataset_scenario['init_model_from'] = ['random_initialization']
                else:
                    dataset_scenario['init_model_from'] = list_scenario['dataset_name'][dataset_name]
                config_dataset.append(dataset_scenario)
        else:
            config_dataset.append(list_scenario)

    for list_scenario in config_dataset:
        params_name = list_scenario.keys()
        params_list = list(list_scenario.values())
        for el in product(*params_list):
            scenario = dict(zip(params_name, el))
            if scenario['partners_count'] != len(scenario['amounts_per_partner']):
                raise Exception("Length of amounts_per_partner does not match number of partners.")
            if scenario['samples_split_option'][0] == 'advanced' \
                    and (scenario['partners_count'] != len(scenario['samples_split_option'][1])):
                raise Exception("Length of samples_split_option does not match number of partners.")
            if 'corrupted_datasets' in params_name:
                if scenario['partners_count'] != len(scenario['corrupted_datasets']):
                    raise Exception("Length of corrupted_datasets does not match number of partners.")
            scenario_params_list.append(scenario)

    logger.info(f"Number of scenario(s) configured: {len(scenario_params_list)}")
    return scenario_params_list


def init_result_folder(yaml_filepath, cfg):
    """
    Init the result folder.

    Args:
        yaml_filepath : str
        cfg

    Returns:
        folder_name
    """

    logger.info("Init result folder")

    now = datetime.datetime.now()
    now_str = now.strftime("%Y-%m-%d_%Hh%M")

    full_experiment_name = cfg["experiment_name"] + "_" + now_str
    experiment_path = Path.cwd() / constants.EXPERIMENTS_FOLDER_NAME / full_experiment_name

    # Check if experiment folder already exists
    while experiment_path.exists():
        logger.warning(f"Experiment folder, {experiment_path} already exists")
        new_experiment_name = Path(str(experiment_path) + "_bis")
        experiment_path = Path.cwd() / constants.EXPERIMENTS_FOLDER_NAME / new_experiment_name
        logger.warning(f"Experiment folder has been renamed to: {experiment_path}")

    experiment_path.mkdir(parents=True, exist_ok=False)

    cfg["experiment_path"] = experiment_path
    logger.info("experiment folder " + str(experiment_path) + " created.")

    target_yaml_filepath = experiment_path / Path(yaml_filepath).name
    copyfile(yaml_filepath, target_yaml_filepath)

    logger.info("Result folder initiated")
    return cfg


def init_gpu_config():
    gpus = tf.config.experimental.list_physical_devices("GPU")
    if gpus:
        logger.info(f"Found GPU: {gpus[0].name}")
        tf.config.experimental.set_memory_growth(gpus[0], True)
        tf.config.experimental.set_virtual_device_configuration(
            gpus[0],
            [tf.config.experimental.VirtualDeviceConfiguration(memory_limit=constants.GPU_MEMORY_LIMIT_MB)]
        )
    else:
        logger.info("No GPU found")


def get_config_from_file(config_filepath):
    config = load_cfg(config_filepath)
    config = init_result_folder(config_filepath, config)

    return config


def parse_command_line_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", help="input config file")
    parser.add_argument("-v", "--verbose", help="verbose output", action="store_true")
    args = parser.parse_args()

    return args


class StreamToLogger:
    def __init__(self, level="INFO"):
        self._level = level

    def write(self, buffer):
        for line in buffer.rstrip().splitlines():
            logger.opt(depth=1).log(self._level, line.rstrip())

    def flush(self):
        pass


def init_logger(args):
    logger.remove()

    # Forward logging to standard output
    if args.verbose:
        logger.add(sys.__stdout__, level="DEBUG")
    else:
        logger.add(sys.__stdout__, level="INFO")

    stream = StreamToLogger()

    info_logger_id = logger.add(constants.INFO_LOGGING_FILE_NAME, level="INFO")
    info_debug_id = logger.add(constants.DEBUG_LOGGING_FILE_NAME, level="DEBUG")
    return stream, info_logger_id, info_debug_id


def move_log_file_to_experiment_folder(logger_id, experiment_path, filename, level):
    logger.remove(logger_id)
    new_log_path = experiment_path / filename
    shutil.move(filename, new_log_path)
    logger.add(new_log_path, level=level)
