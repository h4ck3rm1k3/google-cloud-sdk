# Copyright 2014 Google Inc. All Rights Reserved.
"""Command for adding a backend to a backend service."""
import copy

from googlecloudapis.compute.v1 import compute_v1_messages as messages
from googlecloudsdk.calliope import exceptions
from googlecloudsdk.compute.lib import base_classes

BALANCING_MODES = sorted(
    messages.Backend.BalancingModeValueValuesEnum.to_dict().keys())


class AddBackend(base_classes.ReadWriteCommand):
  """Add a backend to a backend service."""

  @staticmethod
  def Args(parser):
    parser.add_argument(
        '--description',
        help='An optional, textual description for the backend.')

    parser.add_argument(
        '--group',
        required=True,
        help=('The name of a Google Cloud Resource View that can receive '
              'traffic.'))

    parser.add_argument(
        '--zone',
        required=True,
        help='The zone of the Resource View.')

    balancing_mode = parser.add_argument(
        '--balancing-mode',
        choices=BALANCING_MODES,
        help='Defines the strategy for balancing load.')
    balancing_mode.detailed_help = """\
        Defines the strategy for balancing load. ``UTILIZATION'' will
        rely on the CPU utilization of the tasks in the group when
        balancing load. When using ``UTILIZATION'',
        ``--max-utilization'' can be used to set a maximum, target CPU
        utilization for each task. ``RATE'' will spread load based
        on how many queries per second (QPS) the group can
        handle. There are two ways to specify max QPS: ``--max-rate''
        which defines the max QPS for the whole group or
        ``--max-rate-per-task'' which defines the max QPS on a
        per-task basis.
        +
        In ``UTILIZATION'', by default, the group may receive more
        requests than it can handle. To start dropping requests when
        the max utilization is reached, specify ``--max-rate'' or
        ``--max-rate-per-task''.
        """

    max_utilization = parser.add_argument(
        '--max-utilization',
        type=float,
        help=('The target CPU utilization of the group as a '
              'float in the range [0.0, 1.0].'))
    max_utilization.detailed_help = """\
        The target CPU utilization for the group as a float in the
        range [0.0, 1.0]. This flag can only be provided when the
        balancing mode is ``UTILIZATION''.
        """

    rate_group = parser.add_mutually_exclusive_group()

    rate_group.add_argument(
        '--max-rate',
        type=int,
        help='Maximum queries per second (QPS) that the group can handle.')

    rate_group.add_argument(
        '--max-rate-per-instance',
        type=float,
        help='The maximum per-instance queries per second (QPS).')

    capacity_scaler = parser.add_argument(
        '--capacity-scaler',
        type=float,
        help=('A float in the range [0.0, 1.0] that scales the maximum '
              'parameters for the group (e.g., max rate).'))
    capacity_scaler.detailed_help = """\
        A float in the range [0.0, 1.0] that scales the maximum
        parameters for the group (e.g., max rate). A value of 0.0 will
        cause no requests to be sent to the group (i.e., it adds the
        group in a ``drained'' state). The default is 1.0.
        """

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

    for backend in existing.backends:
      if group_uri == backend.group:
        raise exceptions.ToolException(
            'Backend [{0}] in zone [{1}] already exists in backend service '
            '[{2}].'.format(args.group, args.zone, args.name))

    if args.balancing_mode:
      balancing_mode = messages.Backend.BalancingModeValueValuesEnum(
          args.balancing_mode)
    else:
      balancing_mode = None

    backend = messages.Backend(
        balancingMode=balancing_mode,
        capacityScaler=args.capacity_scaler,
        description=args.description,
        group=group_uri,
        maxRate=args.max_rate,
        maxRatePerInstance=args.max_rate_per_instance,
        maxUtilization=args.max_utilization)

    replacement.backends.append(backend)
    return replacement


AddBackend.detailed_help = {
    'brief': 'Add a backend to a backend service',
    'DESCRIPTION': """
        *{command}* is used to add a backend to a backend service. A
        backend is a group of tasks that can handle requests sent to a
        backend service. Currently, the group of tasks can be one or
        more Google Compute Engine virtual machine instances grouped
        together using a resource view.

        Traffic is spread across the backends using
        waterfall-by-location. That is, a request is routed to the
        closest backend that has capacity. If the closest backend has
        reached its capacity, the second closest backend is chosen,
        and so on.

        To modify the parameters of a backend after it has been added
        to the backend service, use 'gcloud compute backend-services
        edit'.
        """,
}
