# Copyright 2014 Google Inc. All Rights Reserved.
"""Command for getting networks."""
from googlecloudsdk.compute.lib import base_classes


class Get(base_classes.GlobalGetter):
  """Get Google Compute Engine networks."""

  @staticmethod
  def Args(parser):
    base_classes.GlobalGetter.Args(parser)
    base_classes.AddFieldsFlag(parser, 'networks')

  @property
  def service(self):
    return self.context['compute'].networks

  @property
  def resource_type(self):
    return 'networks'


Get.detailed_help = {
    'brief': 'Get Google Compute Engine networks',
    'DESCRIPTION': """\
        *{command}* displays all data associated with Google Compute
        Engine networks in a project.
        """,
}
