# Copyright 2014 Google Inc. All Rights Reserved.
"""Command for getting disk types."""
from googlecloudsdk.compute.lib import base_classes


class Get(base_classes.ZonalGetter):
  """Get Google Compute Engine disk types."""

  @staticmethod
  def Args(parser):
    base_classes.ZonalGetter.Args(parser)
    base_classes.AddFieldsFlag(parser, 'diskTypes')

  @property
  def service(self):
    return self.context['compute'].diskTypes

  @property
  def resource_type(self):
    return 'diskTypes'


Get.detailed_help = {
    'brief': 'Get Google Compute Engine disk types',
    'DESCRIPTION': """\
        *{command}* displays all data associated with Google Compute
        Engine disk types in a project.

        By default, disk types from all zones are fetched. The results can
        be narrowed down by providing ``--zone''.
        """,
}
