# Copyright 2014 Google Inc. All Rights Reserved.
"""Facilities for user prompting for request context."""

import abc

from googlecloudsdk.calliope import exceptions
from googlecloudsdk.compute.lib import lister
from googlecloudsdk.compute.lib import utils
from googlecloudsdk.core import resources
from googlecloudsdk.core.util import console_io


class ScopePrompter(object):
  """A mixin class prompting in the case of ambiguous resource context."""

  __metaclass__ = abc.ABCMeta

  def FetchChoices(self, attribute, service):
    """Returns a list of choices used to prompt with."""
    errors = []
    global_resources = lister.GetGlobalResources(
        resource_service=service,
        project=self.context['project'],
        requested_name_regexes=None,
        http=self.context['http'],
        batch_url=self.context['batch-url'],
        errors=errors)

    choices = [resource.name for resource in global_resources]
    if errors:
      utils.RaiseToolException(errors, 'Unable to fetch a list of {0}s. '
                               'Specifying [--{0}] may fix this issue.'
                               .format(attribute))
    if not choices:
      raise exceptions.ToolException(
          'Unable to fetch a list of {0}s. Try again later.'.format(attribute))

    return choices

  def PromptForScope(self, ambiguous_refs, attribute, service):
    """Prompts the user to resolve abiguous resources."""
    # Resource names should be surrounded by brackets while choices should not
    names = ['[{0}]'.format(name) for name, _ in ambiguous_refs]
    choices = sorted(self.FetchChoices(attribute, service))
    title = utils.ConstructList('For the following resources:', names)
    idx = console_io.PromptChoice(
        options=choices,
        message='{0}choose a {1}:'.format(title, attribute))
    if idx is None:
      raise exceptions.ToolException(
          'Unable to prompt. Specify the [--{0}] flag.'.format(attribute))
    choice = choices[idx]
    for _, resource_ref in ambiguous_refs:
      setattr(resource_ref, attribute, choice)

  def CreateScopedReferences(self, resource_names, scope_name, scope,
                             scope_service):
    """Returns a list of resolved resource references for scoped resources."""
    resource_refs = []
    ambiguous_refs = []
    for resource_name in resource_names:
      resource_ref = resources.Parse(
          resource_name,
          collection='compute.{0}'.format(self.prompting_resource_type),
          params={scope_name: scope},
          resolve=False)
      resource_refs.append(resource_ref)
      if not getattr(resource_ref, scope_name):
        ambiguous_refs.append((resource_name, resource_ref))

    if ambiguous_refs and not scope:
      # We need to prompt.
      self.PromptForScope(ambiguous_refs, scope_name, scope_service)

    for resource_ref in resource_refs:
      resource_ref.Resolve()

    return resource_refs

  def CreateZonalReferences(self, resource_names, scope):
    """Returns a list of resolved zonal resource references."""
    if scope:
      zone_ref = resources.Parse(scope, collection='compute.zones')
      zone_name = zone_ref.Name()
    else:
      zone_name = None

    return self.CreateScopedReferences(
        resource_names,
        scope_name='zone',
        scope=zone_name,
        scope_service=self.context['compute'].zones)

  def CreateZonalReference(self, resource_name, scope):
    return self.CreateZonalReferences([resource_name], scope)[0]

  def CreateRegionalReferences(self, resource_names, scope):
    """Returns a list of resolved regional resource references."""
    if scope:
      region_ref = resources.Parse(scope, collection='compute.regions')
      region_name = region_ref.Name()
    else:
      region_name = None

    return self.CreateScopedReferences(
        resource_names,
        scope_name='region',
        scope=region_name,
        scope_service=self.context['compute'].regions)

  def CreateRegionalReference(self, resource_name, scope):
    return self.CreateRegionalReferences([resource_name], scope)[0]

  def CreateGlobalReferences(self, resource_names):
    """Returns a list of resolved global resource references."""
    resource_refs = []
    for resource_name in resource_names:
      resource_refs.append(resources.Parse(
          resource_name,
          collection='compute.{0}'.format(self.prompting_resource_type)))
    return resource_refs
