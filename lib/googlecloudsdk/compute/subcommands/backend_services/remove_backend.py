# Copyright 2014 Google Inc. All Rights Reserved.
"""Command for removing a backend from a backend service."""
import copy

from googlecloudapis.compute.v1 import compute_v1_messages as messages
from googlecloudsdk.calliope import exceptions
from googlecloudsdk.compute.lib import base_classes


class RemoveBackend(base_classes.ReadWriteCommand):
  """Remove a backend frome a backend service."""

  @staticmethod
  def Args(parser):
    parser.add_argument(
        '--group',
        required=True,
        help=('The name of a Google Cloud Resource View used by the backend '
              'to be removed.'))

    parser.add_argument(
        '--zone',
        required=True,
        help='The zone of the backend to be removed.')

    parser.add_argument(
        'name',
        help='The name of the backend service.')

  @property
  def service(self):
    return self.context['compute'].backendServices

  @property
  def resource_type(self):
    return 'backendServices'

  def GetGetRequest(self, args):
    return (self.service,
            'Get',
            messages.ComputeBackendServicesGetRequest(
                backendService=args.name,
                project=self.context['project']))

  def GetSetRequest(self, args, replacement, existing):
    return (self.service,
            'Update',
            messages.ComputeBackendServicesUpdateRequest(
                backendService=args.name,
                backendServiceResource=replacement,
                project=self.context['project']))

  def Modify(self, args, existing):
    replacement = copy.deepcopy(existing)

    group_uri = self.context['resource-views-uri-builder'].Build(
        'zones', args.zone, 'resourceViews', args.group)

    backend_idx = None
    for i, backend in enumerate(existing.backends):
      if group_uri == backend.group:
        backend_idx = i

    if backend_idx is None:
      raise exceptions.ToolException(
          'Backend [{0}] in zone [{1}] is not a backend of backend service '
          '[{2}].'.format(args.group, args.zone, args.name))
    else:
      replacement.backends.pop(backend_idx)

    return replacement


RemoveBackend.detailed_help = {
    'brief': 'Remove a backend from a backend service',
    'DESCRIPTION': """
        *{command}* is used to remove a backend from a backend
        service.

        Before removing a backend, it is a good idea to "drain" the
        backend first. A backend can be drained by setting its
        capacity scaler to zero through 'gcloud compute
        backend-services edit'.
        """,
}
