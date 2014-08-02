# Copyright 2014 Google Inc. All Rights Reserved.
"""Command for getting a target pool's health."""
from googlecloudapis.compute.v1 import compute_v1_messages as messages
from googlecloudsdk.compute.lib import base_classes
from googlecloudsdk.compute.lib import request_helper
from googlecloudsdk.compute.lib import utils


class GetHealth(base_classes.BaseGetter):
  """Get the health of instances in a target pool."""

  @staticmethod
  def Args(parser):
    base_classes.BaseGetter.Args(parser, add_name_regex_arg=False)
    base_classes.AddFieldsFlag(parser, 'targetPoolInstanceHealth')

    utils.AddRegionFlag(
        parser,
        resource_type='target pool',
        operation_type='get health information for')

    parser.add_argument(
        'name',
        help='The name of the target pool.')

  @property
  def service(self):
    return self.context['compute'].targetPools

  @property
  def resource_type(self):
    return 'targetPoolInstanceHealth'

  @property
  def prompting_resource_type(self):
    return 'targetPools'

  def GetTargetPool(self):
    """Fetches the target pool resource."""
    objects = list(request_helper.MakeRequests(
        requests=[(self.service,
                   'Get',
                   messages.ComputeTargetPoolsGetRequest(
                       project=self.context['project'],
                       region=self.target_pool_ref.region,
                       targetPool=self.target_pool_ref.Name()))],
        http=self.context['http'],
        batch_url=self.context['batch-url']))

    return objects[0]

  def GetResources(self, args, errors):
    """Returns a list of TargetPoolInstanceHealth objects."""
    self.target_pool_ref = self.CreateRegionalReference(args.name, args.region)
    target_pool = self.GetTargetPool()
    instances = target_pool.instances

    # If the target pool has no instances, we should return an empty
    # list.
    if not instances:
      return []

    requests = []
    for instance in instances:
      request_message = messages.ComputeTargetPoolsGetHealthRequest(
          instanceReference=messages.InstanceReference(
              instance=instance),
          project=self.context['project'],
          region=self.target_pool_ref.region,
          targetPool=self.target_pool_ref.Name())
      requests.append((self.service, 'GetHealth', request_message))

    return request_helper.MakeRequests(
        requests=requests,
        http=self.context['http'],
        batch_url=self.context['batch-url'])


GetHealth.detailed_help = {
    'brief': 'Get the health of instances in a target pool',
    'DESCRIPTION': """\
        *{command}* displays the health of instances in a target pool.
        """,
}
