'''
Hyperparameters.py
Version 1.0
Written using Python 2.7.12
@ Matt Golub, August 2018.
Please direct correspondence to mgolub@stanford.edu.
'''

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import pdb
from copy import deepcopy
import hashlib
import pickle as cPickle
from numpy import sort
import yaml
import numpy as np

class Hyperparameters(object):
    '''A general class for managing a model's hyperparameters, default
    settings, and hashes for organizing model checkpoint directories.

    '''
    def __init__(self,
                 hps=None,
                 default_hash_hps=None,
                 default_non_hash_hps=None,
                 hash_len=10,
                 verbose=False):
        '''Creates a Hyperparameters object.

        The resulting object contains hyperparameters as class attributes,
        with default values overridden by the settings in hps.

        Args:
            hps: dict containing hyperparameter names as keys and
            corresponding settings as values. These settings are used to
            override default values. All values must be also included in either
            default_hash_hps or default_non_hash_hps. Default: None.

            default_hash_hps: dict containing hyperparameters and their
            default values for the set of hyperparameters to be hashed. These
            hyperparameters may affect the model architecture or the
            trajectory of fitting, and as such are typically swept during
            hyperparameter optimization.

            default_non_hash_hps: dict containing hyperparameters and their
            default values for the set of hyperparameters that are not
            included in the hash. These hyperparameters should not influence
            the model architecture or the trajectory of fitting.

            hash_len (optional): int between 1 and 512 specifying the number
            of hex characters to include in the hyperparameters hash (all
            others are truncated). Larger values in this range may be
            necessary for massive hyperparameter searches, where the
            likelihood of hash collisions may be non-negligible. Default: 10.

            verbose (optional): bool indicating whether to print status
            updates. Default: False.

        Returns:
            None.

        Raises:
            ValueError if at least one default_hash_hps or
            default_non_hash_hps is not specified.
        '''
        if default_hash_hps is None and default_non_hash_hps is None:
            raise ValueError('At lease one of default_hash_hps and '
                'default_non_hash_hps must be specified, but both were None.')

        self._hash_len = hash_len
        self._verbose = verbose
        self._all_hps_as_dict, self._hash_hps_as_dict = \
            self._parse(hps, default_hash_hps, default_non_hash_hps)

        for key, val in self._all_hps_as_dict.items():
            setattr(self, key, val)

    def __dict__(self):
        '''Returns hyperparameters in a dict.

        Args:
            None.

        Returns:
            dict of all hyperparameter names and settings as key, value pairs.
        '''
        return self._all_hps_as_dict

    def get_hash(self):
        '''Computes a hash of all non-default hash hyperparameters.

        In most applications (e.g., setting up run directories), this is the
        hash that should be used. By omitting default hps, hashes become more
        robust to future updates to an algorithm--if new hps are introduced,
        and their default values are chosen to reproduce before-update
        behavior, before-update and after-update hashes will be compatible.

        Args:
            None.

        Returns:
            string containing the hyperparameters hash.
        '''
        return self._generate_hash(self._hash_hps_as_dict)[0:self._hash_len]

    def get_hash_all_hps(self):
        '''Computes a hash of all hyperparameters, including default and
        non-hash hyperparameters.

        Args:
            None.

        Returns:
            string containing the hyperparameters hash.
        '''
        return self._generate_hash(self._all_hps_as_dict)[0:self._hash_len]

    def _parse(self, input_hps, default_hash_hps, default_non_hash_hps):
        '''Parses the input arguments to __init__, returning a dict of all hps
        and a dict of hps to be hashed.

        Args:
            input_hps: See comment for hps in __init__.

            default_hash_hps: See comment for the same arg in __init__.

            default_non_hash_hps: See comment for the same arg in __init__.

        Returns:
            hps: dict containing all hyperparameters set to defaults, except
            as overridden by values in hps.

            hps_to_hash: dict containing the subset of hyperparameters in
            input_hps that are to be hashed (i.e., keys with non-default
            values that are also keys in default_hash_hps).

        Raises:
            ValueError if any key in input_hps is not included in exactly one
            of default_hash_hps or default_non_hash_hps.
        '''

        # Check to make sure each hp is either hash or non-hash (NOT BOTH)
        default_hash_hp_keys = default_hash_hps.keys()
        for non_hash_key in default_non_hash_hps.keys():
            if non_hash_key in default_hash_hp_keys:
                raise ValueError('Hyperparameter [%s] cannot be both hash '
                    'and non-hash.' % non_hash_key)

        # Combine default hash and default non-hash hps
        default_hps = default_hash_hps
        default_hps.update(default_non_hash_hps)

        # Initialize hps with default values
        hps = deepcopy(default_hps)
        hps_to_hash = dict()


        # Add non-default entries to dict for hashing
        for key, val in input_hps.items():
            # Allows for 'None' to be used in command line arguments.
            if val == 'None':
                val = None

            # Check to make sure all input_hps are valid
            # (i.e., have default values)
            # Otherwise, user may have mistyped an hp name.
            if not key in default_hps:
                raise ValueError('%s is not a valid hyperparameter '
                    '(has no specified default).' % key)
            else:
                # If valid, overwrite default values with input values
                hps[key] = val

                # If this hp should be hashed and value is not default, add it
                # to the dict for hashing
                if (key in default_hash_hp_keys) and np.all(val != default_hps[key]):
                    hps_to_hash[key] = val

        return hps, hps_to_hash

    def _sorted_str_from_dict(self, d):
        '''Creates a string of the key, value pairs in dict d, sorted by key.
        Sorting is required to 'uniquify' any set of hyperparameter settings
        (because two different orderings of the same hyperparameter settings
        are assumed to result in identical model and fitting behavior).

        Args:
            d: dict of hyperparameters.

        Returns:
            string of key, value pairs, sorted by key.
        '''

        sorted_keys = sort(list(d.keys()))
        n_keys = len(sorted_keys)

        str_items = ['{']
        key_idx = 1
        for key in sorted_keys:
            val = d[key]

            if isinstance(val, dict):
                str_val = self._sorted_str_from_dict(val)
            else:
                str_val = str(val)

            new_entry = (str(key) + ': ' + str_val)
            str_items.append(new_entry)

            if key_idx < n_keys:
                str_items.append(', ')

            key_idx += 1

        str_items.append('}')

        return ''.join(str_items)

    def _generate_hash(self, hps):
        '''Generates a hash from a unique string representation of the
        hyperparameters in hps.

        Args:
            hps: dict of hyperparameter names and settings as keys and values.

        Returns:
            string containing 512-bit hash in hexadecimal representation.
        '''
        str_to_hash = self._sorted_str_from_dict(hps)
        print(str_to_hash)
        # Generate the hash for that string
        h = hashlib.new('sha512')
        h.update(str_to_hash.encode('utf-8'))
        hps_hash = h.hexdigest()

        return hps_hash

    def write_yaml(self, save_path):
        # Note, this doesn't do well with numpy variables.
        # Ideally, make sure everything is bool, int, float, string, etc.
        self._maybe_print('Writing Hyperparameters YAML file.')
        with open(save_path, 'w') as yaml_file:
            yaml.dump(self._all_hps_as_dict,
                      yaml_file,
                      default_flow_style=False)

    def restore_from_yaml(self, yaml_path):
        # Note, this returns a dict of hps, not a Hyperparameters object
        # This is for use on runs created before save/restore was implemented
        # Preferred usage is with save/restore

        self._maybe_print('Reading Hyperparameters YAML file.')
        with open(yaml_path, 'r') as yaml_file:
            return yaml.load(yaml_file)

    def save(self, save_path):
        '''Saves the Hyperparameters object.

        Args:
            save_path: string containing the path at which to save these
            hyperparameter settings (including filename and arbitrary
            extension).

        Returns:
            None.
        '''
        self._maybe_print('Saving Hyperparameters.')
        file = open(save_path, 'wb')
        file.write(cPickle.dumps(self._all_hps_as_dict))
        file.close()

    def _maybe_print(self, s):
        '''Depending on verbosity level, print a status update.

        Args:
            s: string containing a status update.

        Returns:
            None.
        '''
        if self._verbose:
            print(s)

    @staticmethod
    def restore(restore_path):
        '''Loads hyperparameters from a saved Hyperparameters object.

        Args:
            restore_path:
                string containing the path of a previously saved
                Hyperparameters object (including filename and extension).

        Returns:
            dict containing all hyperparameter names and settings from the
            previously saved Hyperparameters object.
        '''
        file = open(restore_path, 'rb')
        restore_data = file.read()
        file.close()
        return cPickle.loads(restore_data)

    @staticmethod
    def parse_command_line(default_hps, description=None):
        '''Parses command-line arguments into a dict of hyperparameters.

        Args:
            default_hps: dict specifying all default hyperparameter settings.
            All values must have type bool, int, float, str, or dict. Values
            that are dicts must themselves have values of only the
            aforementioned types.

                Nesting of dicts is supported at the command line using
                colon delimiters, e.g.:

                    python your_script.py --d1:d2:n 10

                will update the value in default_hps['d1']['d2']['n'] to be 10.

            description (optional): string containing text to display if help
            commands (-h, --help) are invoked at the command line. See
            argparse.ArugmentParser for further details. Default: None.

        Returns:
            dict matching default_hps, but with values replaced by any
            corresponding values provided at the command line.
        '''

        def str2bool(v):
            if v.lower() in ('yes', 'true', 't', 'y', '1'):
                return True
            elif v.lower() in ('no', 'false', 'f', 'n', '0'):
                return False
            else:
                raise argparse.ArgumentTypeError('Boolean value expected.')

        def parse_helper(D, str_prefix=''):
            '''
            Validates value types and recurses appropriately when encountering
            colon delimiters in keys.

            Args:
                D: dict containing default hyperparameter values. Values must
                be of type bool, int, float, str, or dict.

            Returns:
                None.
            '''
            for key, val in D.items():

                if val is None or val=='None':
                    # Don't set default. This results in default set to None.
                    # setting default=None can result in default='None' (bad).
                    parser.add_argument('--' + str_prefix + str(key))

                elif isinstance(val, bool) or \
                    isinstance(val, int) or \
                    isinstance(val, float) or \
                    isinstance(val, str):

                    if isinstance(val, bool):
                        type_val = str2bool
                    elif val is not None:
                        type_val = type(val)

                    parser.add_argument('--' + str_prefix + str(key),
                        default=val, type=type_val)

                elif isinstance(val, dict):
                    # Recursion
                    parse_helper(val, str_prefix=str_prefix + str(key) + ':')

                else:
                    raise argparse.ArgumentTypeError('Default value must be '
                        'bool, int, float, str, dict, or None, but was %s. ' %
                        type(val))

        def reconstruct_helper(D_flat):
            '''
            Args:
                D_flat: dict containing default hyperparameters, with values
                replaced by any corresponding values provided at the command
                line. Values must be of type bool, int, float, or str (no
                dicts allowed).

            Returns:
                D_unflattened: dict, nested with other dicts as specified by
                colon delimitting in keys of D_flat.
            '''

            def parse_key(key):
                '''
                Args:
                    key is string containing at least 1 colon.

                Returns:
                    dict_name: key up to (but not including) the first colon.

                    rem_key: key from first char after colon to end.
                '''
                if not ':' in key:
                    raise ValueError('key does not contain delimitting colon.')

                first_colon_idx = key.index(':')
                dict_name = key[:first_colon_idx]
                rem_key = key[(first_colon_idx + 1):]

                return dict_name, rem_key

            def assign_leaf(key, val):
                '''
                Handles the case where we are writing the first entry of a
                potentially nested dict. Because it's the first entry, there
                is no chance of overwriting an existing dict.
                '''
                if ':' in key:
                    dict_name, rem_key = parse_key(key)
                    return {dict_name: assign_leaf(rem_key, val)}
                else:
                    return {key: val}

            def add_helper(D, key, val):
                if ':' in key:
                    dict_name, rem_key = parse_key(key)

                    if dict_name == 'data_hps':
                        pdb.set_trace()

                    if dict_name in D:
                        D[dict_name] = add_helper(D[dict_name], rem_key, val)
                    else:
                        D[dict_name] = assign_leaf(rem_key, val)
                else:
                    D[key] = val

                return D

            D_unflattened = dict()
            for key, val in D_flat.items():
                # Don't need to check type here (handled by parse_helper).
                D_unflattened = add_helper(D_unflattened, key, val)

            return D_unflattened

        parser = argparse.ArgumentParser(description=description)
        parse_helper(default_hps)

        args = parser.parse_args()

        # This has no dicts (all values are bool, int, float, or str)
        hps_flat = vars(args)

        # Recursively reconstruct any dicts (based on colon delimiters)
        hps = reconstruct_helper(hps_flat)

        return hps
