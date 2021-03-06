# Copyright 2014 Google Inc. All Rights Reserved.
"""Command for getting zones."""
from googlecloudsdk.compute.lib import base_classes


class Get(base_classes.GlobalGetter):
  """Get Google Compute Engine zones."""

  @staticmethod
  def Args(parser):
    base_classes.GlobalGetter.Args(parser)
    base_classes.AddFieldsFlag(parser, 'zones')

  @property
  def service(self):
    return self.context['compute'].zones

  @property
  def resource_type(self):
    return 'zones'


Get.detailed_help = {
    'brief': 'Get Google Compute Engine zones',
    'DESCRIPTION': """\
        *{command}* displays all data associated with Google Compute
        Engine zones.
        """,
}
