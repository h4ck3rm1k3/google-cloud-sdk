# Copyright 2014 Google Inc. All Rights Reserved.
"""Command for getting HTTP health checks."""
from googlecloudsdk.compute.lib import base_classes


class Get(base_classes.GlobalGetter):
  """Display detailed information about HTTP health checks."""

  @staticmethod
  def Args(parser):
    base_classes.GlobalGetter.Args(parser)
    base_classes.AddFieldsFlag(parser, 'httpHealthChecks')

  @property
  def service(self):
    return self.context['compute'].httpHealthChecks

  @property
  def resource_type(self):
    return 'httpHealthChecks'


Get.detailed_help = {
    'brief': 'Display detailed information about HTTP health checks',
    'DESCRIPTION': """\
        *{command}* displays all data associated with Google Compute
        Engine HTTP health checks in a project.
        """,
}
