# Copyright 2014 Google Inc. All Rights Reserved.
"""Defines tool-wide constants."""
import collections
import httplib

BYTES_IN_ONE_GB = 2 ** 30

# The maximum number of results that can be returned in a single list
# response.
MAX_RESULTS_PER_PAGE = 500

# Defaults for instance creation.
DEFAULT_ACCESS_CONFIG_NAME = 'external-nat'

DEFAULT_MACHINE_TYPE = 'n1-standard-1'
DEFAULT_NETWORK = 'default'

DEFAULT_IMAGE = 'debian-7-backports'

ImageAlias = collections.namedtuple('ImageAlias', ['project', 'name_prefix'])

IMAGE_ALIASES = {
    'centos-6': ImageAlias(project='centos-cloud', name_prefix='centos-6'),
    'coreos': ImageAlias(project='coreos-cloud', name_prefix='coreos-beta'),
    'debian-7': ImageAlias(project='debian-cloud',
                           name_prefix='debian-7-wheezy'),
    'debian-7-backports': ImageAlias(project='debian-cloud',
                                     name_prefix='backports-debian-7-wheezy'),
    'opensuse-13': ImageAlias(project='opensuse-cloud',
                              name_prefix='opensuse-13-1'),
    'rhel-6': ImageAlias(project='rhel-cloud', name_prefix='rhel-6'),
    'sles-11': ImageAlias(project='suse-cloud', name_prefix='sles-11'),
}

IMAGE_PROJECTS = [
    'centos-cloud',
    'coreos-cloud',
    'debian-cloud',
    'opensuse-cloud',
    'rhel-cloud',
    'suse-cloud',
]

# SSH-related constants.
DEFAULT_SSH_KEY_FILE = '~/.ssh/google_compute_engine'
SSH_KEYS_METADATA_KEY = 'sshKeys'
MAX_METADATA_VALUE_SIZE_IN_BYTES = 32768
PER_USER_SSH_CONFIG_FILE = '~/.ssh/config'


# Custom help for HTTP error messages.
HTTP_ERROR_TIPS = {
    httplib.UNAUTHORIZED: [
        'Try logging in using [gcloud auth login].'
        ],
    httplib.NOT_FOUND: [
        'Ensure that resources referenced are spelled correctly.',
        ('Ensure that the Google Compute Engine API is enabled for '
         'this project at https://cloud.google.com/console.'),
        ('Ensure that your account is a member of this project at '
         'https://cloud.google.com/console.'),
        'Ensure that any resources referenced exist.',
        ],
    httplib.INTERNAL_SERVER_ERROR: [
        ('These are probably transient errors. Try running the command again '
         'in a few minutes.'),
        ],
    httplib.BAD_REQUEST: [
        'Ensure that you spelled everything correctly.',
        'Ensure that any resources referenced exist.',
        ],
}

_STORAGE_RO = 'https://www.googleapis.com/auth/devstorage.read_only'

DEFAULT_SCOPES = [_STORAGE_RO]

SCOPES = {
    'bigquery': 'https://www.googleapis.com/auth/bigquery',
    'sql': 'https://www.googleapis.com/auth/sqlservice',
    'compute-ro': 'https://www.googleapis.com/auth/compute.readonly',
    'compute-rw': 'https://www.googleapis.com/auth/compute',
    'datastore': 'https://www.googleapis.com/auth/datastore',
    'storage-full': 'https://www.googleapis.com/auth/devstorage.full_control',
    'storage-ro': _STORAGE_RO,
    'storage-rw': 'https://www.googleapis.com/auth/devstorage.read_write',
    'storage-wo': 'https://www.googleapis.com/auth/devstorage.write_only',
    'taskqueue': 'https://www.googleapis.com/auth/taskqueue',
    'userinfo-email': 'https://www.googleapis.com/auth/userinfo.email',
}
