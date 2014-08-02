# Copyright 2014 Google Inc. All Rights Reserved.
"""Command for listing firewalls."""
from googlecloudsdk.compute.lib import base_classes


class List(base_classes.GlobalLister):
  """List Google Compute Engine firewalls."""

  @property
  def service(self):
    return self.context['compute'].firewalls

  @property
  def resource_type(self):
    return 'firewalls'
