# Copyright 2014 Google Inc. All Rights Reserved.
"""Utility functions that don't belong in the other utility modules."""


import cStringIO

from googlecloudsdk.calliope import exceptions as calliope_exceptions
from googlecloudsdk.compute.lib import constants
from googlecloudsdk.core.util import console_io


def ZoneNameToRegionName(zone_name):
  """'Converts zone name to region name: 'us-central1-a' -> 'us-central1'."""
  return zone_name.rsplit('-', 1)[0]


def NormalizeGoogleStorageUri(uri):
  """Converts gs:// to http:// if uri begins with gs:// else returns uri."""
  if uri and uri.startswith('gs://'):
    return 'http://storage.googleapis.com/' + uri[len('gs://'):]
  else:
    return uri


def ConstructList(title, items):
  """Returns a string displaying the items and a title."""
  buf = cStringIO.StringIO()
  printer = console_io.ListPrinter(title)
  printer.Print(sorted(set(items)), output_stream=buf)
  return buf.getvalue()


def RaiseToolException(problems, error_message=None):
  """Raises a ToolException with the given list of messages."""
  tips = []
  errors = []
  for code, message in problems:
    errors.append(message)

    new_tips = constants.HTTP_ERROR_TIPS.get(code)
    if new_tips:
      tips.extend(new_tips)

  if tips:
    advice = ConstructList(
        '\nHere are some tips that may help fix these problems:', tips)
  else:
    advice = ''

  raise calliope_exceptions.ToolException(
      ConstructList(
          error_message or 'Some requests did not succeed:',
          errors) + advice)


def AddZoneFlag(parser, resource_type, operation_type):
  """Adds a --zone flag to the given parser."""
  short_help = 'The zone of the {0} to {1}.'.format(
      resource_type, operation_type)
  zone = parser.add_argument(
      '--zone',
      help=short_help)
  zone.detailed_help = (
      short_help + ' If omitted and the arguments are not all URIs, '
      'you will be prompted to select a zone.')


def AddRegionFlag(parser, resource_type, operation_type):
  """Adds a --region flag to the given parser."""
  short_help = 'The region of the {0} to {1}.'.format(
      resource_type, operation_type)
  region = parser.add_argument(
      '--region',
      help=short_help)
  region.detailed_help = (
      short_help + ' If omitted and the arguments are not all URIs, '
      'you will be prompted to select a region.')
