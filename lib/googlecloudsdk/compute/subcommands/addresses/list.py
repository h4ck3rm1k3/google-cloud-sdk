# Copyright 2014 Google Inc. All Rights Reserved.
"""Command for listing addresses."""
from googlecloudsdk.compute.lib import base_classes


class List(base_classes.RegionalLister):
  """List Google Compute Engine addresses."""

  @property
  def service(self):
    return self.context['compute'].addresses

  @property
  def resource_type(self):
    return 'addresses'
