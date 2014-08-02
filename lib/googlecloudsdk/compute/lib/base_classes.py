# Copyright 2014 Google Inc. All Rights Reserved.
"""Base classes for abstracting away common logic."""
import abc
import collections
import copy
import cStringIO
import itertools
import json
import sys
import textwrap


import protorpc.messages
import yaml

from googlecloudapis.apitools.base.py import encoding
from googlecloudapis.compute.v1 import compute_v1_messages as messages
from googlecloudsdk.calliope import base
from googlecloudsdk.calliope import exceptions as calliope_exceptions
from googlecloudsdk.compute.lib import lister
from googlecloudsdk.compute.lib import metadata_utils
from googlecloudsdk.compute.lib import property_selector
from googlecloudsdk.compute.lib import request_helper
from googlecloudsdk.compute.lib import resource_specs
from googlecloudsdk.compute.lib import scope_prompter
from googlecloudsdk.compute.lib import utils
from googlecloudsdk.core import log
from googlecloudsdk.core import properties
from googlecloudsdk.core.util import console_io
from googlecloudsdk.core.util import edit
from googlecloudsdk.core.util import list_printer
from googlecloudsdk.core.util import resource_printer


def PrintTable(resources, table_cols):
  """Prints a table of the given resources."""
  printer = resource_printer.TablePrinter(out=log.out)

  header = []
  for name, _ in table_cols:
    header.append(name)
  printer.AddRow(header)

  for resource in resources:
    row = []
    for _, action in table_cols:
      if isinstance(action, property_selector.PropertyGetter):
        row.append(action.Get(resource) or '')
      elif callable(action):
        row.append(action(resource))
    printer.AddRow(row)

  printer.Print()


class BaseCommand(base.Command, scope_prompter.ScopePrompter):
  """Base class for all compute subcommands."""

  __metaclass__ = abc.ABCMeta

  def __init__(self, *args, **kwargs):
    super(BaseCommand, self).__init__(*args, **kwargs)

    # Set the default project for resource resolution

    if self.resource_type:
      # Constructing the spec can be potentially expensive (e.g.,
      # generating the set of valid fields from the protobuf message),
      # so we fetch it once in the constructor.
      self._resource_spec = resource_specs.GetSpec(self.resource_type)
    else:
      self._resource_spec = None

  @property
  def transformations(self):
    if self._resource_spec:
      return self._resource_spec.transformations
    else:
      return None

  @property
  def resource_type(self):
    """Specifies the name of the collection that should be printed."""
    return None

  @property
  def prompting_resource_type(self):
    """Specifies the name of the collection that should be prompted for.

    For most commands this is equal to self.resource_type.
    """
    return self.resource_type


class BaseResourceFetcher(BaseCommand):
  """Base class for the get and list subcommands."""

  __metaclass__ = abc.ABCMeta

  @staticmethod
  def Args(parser, add_name_regex_arg=True):
    parser.add_argument(
        '--limit',
        type=int,
        help='The maximum number of results.')

    sort_by = parser.add_argument(
        '--sort-by',
        help='A field to sort by.')
    sort_by.detailed_help = """\
        A field to sort by. To perform a descending-order sort, prefix
        the value of this flag with a tilde (``~'').
        """

    if add_name_regex_arg:
      name_regex = parser.add_argument(
          'name_regex',
          nargs='*',
          default=[],
          help='Name regular expressions used to filter the resources fetched.')
      name_regex.detailed_help = """\
          Name regular expressions used to filter the resources
          fetched. The regular expressions must conform to the re2
          syntax (see
          link:https://code.google.com/p/re2/wiki/Syntax[]).
          """

  @abc.abstractmethod
  def ActuallyRun(self, args):
    """Method to be implemented by subclasses.

    This allows the Run() method of this class definition to do any
    work common to all subclasses such as flag validation.

    Args:
      args: A dictionary representing command-line arguments.
    """

  def Run(self, args):
    if args.limit is not None:
      if args.limit <= 0:
        raise calliope_exceptions.ToolException(
            '[--limit] must be a positive integer; received [{0}].'
            .format(args.limit))

      # A really large value should be treated as if the user does not
      # want to impose a limit.
      if args.limit > sys.maxint:
        args.limit = None

    return self.ActuallyRun(args)

  @abc.abstractmethod
  def GetResources(self, args, errors):
    """Returns a generator of JSON-serializable resource dicts."""


class BaseLister(BaseResourceFetcher):
  """Base class for the list subcommands."""

  __metaclass__ = abc.ABCMeta

  @staticmethod
  def Args(parser):
    BaseResourceFetcher.Args(parser)
    uri = parser.add_argument(
        '--uri',
        action='store_true',
        help='If provided, a list of URIs is printed instead of a table.')
    uri.detailed_help = """\
        If provided, the list command will only print URIs for the
        resources returned.  If this flag is not provided, the list
        command will print a human-readable table of useful resource
        data.
        """

  def ActuallyRun(self, args):
    """Yields JSON-serializable dicts of resources or self links."""
    if args.uri:
      field_selector = None
    else:
      # The field selector should be constructed before any resources
      # are fetched, so if there are any syntactic errors with the
      # fields, we can fail fast.
      field_selector = property_selector.PropertySelector(
          properties=None,
          transformations=self.transformations)

    errors = []
    resources = lister.ProcessResults(
        resources=self.GetResources(args, errors),
        field_selector=field_selector,
        sort_by=args.sort_by,
        limit=args.limit)

    for resource in resources:
      if args.uri:
        yield resource['selfLink']
      else:
        yield resource

    if errors:
      utils.RaiseToolException(errors)

  def Display(self, args, resources):
    """Prints the given resources."""
    if args.uri:
      for resource in resources:
        log.out.Print(resource)
    else:
      PrintTable(resources, self._resource_spec.table_cols)


def AddFieldsFlag(parser, resource_type):
  """Adds the --fields flag to the given parser.

  This function is to be called from implementations of get
  subcommands. The resulting help text of --fields will contain all
  valid values for the flag. We need this function becasue Args() is a
  static method so the only way to communicate the resource type is by
  having the subclass pass it in.

  Args:
    parser: The parser to add --fields to.
    resource_type: The resource type as defined in the resource_specs
      module.
  """

  def GenerateDetailedHelp():
    return ('Fields to display. Possible values are:\n+\n  ' +
            '\n  '.join(resource_specs.GetSpec(resource_type).fields))

  fields = parser.add_argument(
      '--fields',
      nargs='+',
      help='Fields to display.')

  # Note that we do not actually call GenerateDetailedHelp, the help
  # generator does that. This is important because getting the set of
  # fields is a potentially expensive operation, so we only want to do
  # it when needed.
  fields.detailed_help = GenerateDetailedHelp


class BaseDescriber(BaseCommand):
  """Base class for the describe subcommands."""

  __metaclass__ = abc.ABCMeta

  @staticmethod
  def Args(parser):
    parser.add_argument(
        'name',
        metavar='NAME',
        help='The name of the resource to fetch.')

  @property
  def method(self):
    return 'Get'

  def ScopeRequest(self, args, request):
    """Adds a zone or region to the request object if necessary."""

  def Run(self, args):
    """Yields JSON-serializable dicts of resources."""
    # The field selector should be constructed before any resources
    # are fetched, so if there are any syntactic errors with the
    # fields, we can fail fast.
    field_selector = property_selector.PropertySelector(properties=args.fields)
    get_request_class = self.service.GetRequestType(self.method)
    name_field = self.service.GetMethodConfig(self.method).ordered_params[-1]

    request = get_request_class(project=self.context['project'])
    setattr(request, name_field, args.name)
    self.ScopeRequest(args, request)

    get_request = (self.service, self.method, request)
    objects = request_helper.MakeRequests(
        requests=[get_request],
        http=self.context['http'],
        batch_url=self.context['batch-url'])

    resources = list(lister.ProcessResults(objects, field_selector))
    return resources[0]

  def Display(self, args, resources):
    """Prints the given resources."""
    resource_printer.Print(
        resources=resources,
        print_format='yaml',
        out=log.out)


class BaseGetter(BaseResourceFetcher):
  """Base class for the get subcommands."""

  __metaclass__ = abc.ABCMeta

  @staticmethod
  def Args(parser, add_name_regex_arg=True):
    BaseResourceFetcher.Args(parser, add_name_regex_arg=add_name_regex_arg)

  def ActuallyRun(self, args):
    """Yields JSON-serializable dicts of resources."""
    # The field selector should be constructed before any resources
    # are fetched, so if there are any syntactic errors with the
    # fields, we can fail fast.
    field_selector = property_selector.PropertySelector(
        properties=args.fields,
        transformations=None)

    errors = []
    resources = lister.ProcessResults(
        resources=self.GetResources(args, errors),
        field_selector=field_selector,
        sort_by=args.sort_by,
        limit=args.limit)

    for resource in resources:
      yield resource

    if errors:
      utils.RaiseToolException(errors)

  def Display(self, args, resources):
    """Prints the given resources."""
    resource_printer.Print(
        resources=resources,
        print_format='yaml',
        out=log.out)


class GlobalResourceFetcherMixin(object):
  """Mixin class for global resources."""

  def GetResources(self, args, errors):
    return lister.GetGlobalResources(
        resource_service=self.service,
        project=properties.VALUES.core.project.Get(required=True),
        requested_name_regexes=args.name_regex,
        http=self.context['http'],
        batch_url=self.context['batch-url'],
        errors=errors)


class GlobalLister(GlobalResourceFetcherMixin, BaseLister):
  """Base class for listing global resources."""


class GlobalGetter(GlobalResourceFetcherMixin, BaseGetter):
  """Base class for getting global resources."""


class GlobalDescriber(BaseDescriber):
  """Base class for describing global resources."""


class RegionalResourceFetcherMixin(object):
  """Mixin class for regional resources."""

  def GetResources(self, args, errors):
    compute = self.context['compute']
    return lister.GetRegionalResources(
        regions_service=compute.regions,
        resource_service=self.service,
        project=properties.VALUES.core.project.Get(required=True),
        requested_regions=args.regions,
        requested_name_regexes=args.name_regex,
        http=self.context['http'],
        batch_url=self.context['batch-url'],
        errors=errors)


class RegionalLister(RegionalResourceFetcherMixin, BaseLister):
  """Base class for listing regional resources."""

  @staticmethod
  def Args(parser):
    BaseLister.Args(parser)
    parser.add_argument(
        '--regions',
        metavar='REGION',
        help='If provided, only resources from the given regions are queried.',
        nargs='+',
        default=[])


class RegionalGetter(RegionalResourceFetcherMixin, BaseGetter):
  """Base class for getting regional resources."""

  @staticmethod
  def Args(parser):
    BaseGetter.Args(parser)
    parser.add_argument(
        '--regions',
        metavar='REGION',
        help='If provided, only resources from the given regions are queried.',
        nargs='+',
        default=[])


class RegionalDescriber(BaseDescriber):
  """Base class for describing regional resources."""

  @staticmethod
  def Args(parser):
    BaseDescriber.Args(parser)
    parser.add_argument(
        '--region',
        help='The region of the resource.',
        required=True)

  def ScopeRequest(self, args, request):
    request.region = args.region


class ZonalResourceFetcherMixin(object):
  """Mixin class for zonal resources."""

  def GetResources(self, args, errors):
    compute = self.context['compute']
    return lister.GetZonalResources(
        zones_service=compute.zones,
        resource_service=self.service,
        project=properties.VALUES.core.project.Get(required=True),
        requested_zones=args.zones,
        requested_name_regexes=args.name_regex,
        http=self.context['http'],
        batch_url=self.context['batch-url'],
        errors=errors)


class ZonalLister(ZonalResourceFetcherMixin, BaseLister):
  """Base class for listing zonal resources."""

  @staticmethod
  def Args(parser):
    BaseLister.Args(parser)
    parser.add_argument(
        '--zones',
        metavar='ZONE',
        help='If provided, only resources from the given zones are queried.',
        nargs='+',
        default=[])


class ZonalGetter(ZonalResourceFetcherMixin, BaseGetter):
  """Base class for getting zonal resources."""

  @staticmethod
  def Args(parser):
    BaseGetter.Args(parser)
    parser.add_argument(
        '--zones',
        metavar='ZONE',
        help='If provided, only resources from the given zones are queried.',
        nargs='+',
        default=[])


class ZonalDescriber(BaseDescriber):
  """Base class for describing zonal resources."""

  @staticmethod
  def Args(parser):
    BaseDescriber.Args(parser)
    parser.add_argument(
        '--zone',
        help='The zone of the resource.',
        required=True)

  def ScopeRequest(self, args, request):
    request.zone = args.zone


class BaseAsyncMutator(BaseCommand):
  """Base class for subcommands that mutate resources."""

  __metaclass__ = abc.ABCMeta

  @abc.abstractproperty
  def service(self):
    """The service that can mutate resources."""

  @property
  def custom_get_requests(self):
    """Returns request objects for getting the mutated resources.

    This should be a dict mapping operation targetLink names to
    requests that can be passed to batch_helper. This is useful for
    verbs whose operations do not point to the resources being mutated
    (e.g., Disks.createSnapshot).

    If None, the operations' targetLinks are used to fetch the mutated
    resources.
    """
    return None

  @abc.abstractproperty
  def method(self):
    """The method name on the service as a string."""

  @abc.abstractmethod
  def CreateRequests(self, args):
    """Creates the requests that perform the mutation.

    It is okay for this method to make calls to the API as long as the
    calls originating from this method do not cause any mutations.

    Args:
      args: The command-line arguments.

    Returns:
      A list of request protobufs.
    """

  def Run(self, args):
    request_protobufs = self.CreateRequests(args)
    requests = [
        (self.service, self.method, request) for request in request_protobufs]

    resources = request_helper.MakeRequests(
        requests=requests,
        http=self.context['http'],
        batch_url=self.context['batch-url'],
        custom_get_requests=self.custom_get_requests)

    resources = lister.ProcessResults(
        resources=resources,
        field_selector=property_selector.PropertySelector(
            properties=None,
            transformations=self.transformations))
    for resource in resources:
      yield resource

  def Display(self, _, resources):
    """Prints the given resources."""
    # The following try/except ensures that we only call
    # resource_printer.Print if there is as least one item in the
    # resources generator.
    try:
      head = next(resources)
      resources = itertools.chain([head], resources)
      resource_printer.Print(
          resources=resources,
          print_format='yaml',
          out=log.out)
    except StopIteration:
      pass


class BaseAsyncCreator(BaseAsyncMutator):
  """Base class for subcommands that create resources."""

  def Display(self, _, resources):
    list_printer.PrintResourceList(
        'compute.' + self.resource_type,
        resources)


class BaseDeleter(BaseAsyncMutator):
  """Base class for deleting resources."""

  @staticmethod
  def Args(parser):
    BaseAsyncMutator.Args(parser)
    parser.add_argument(
        'names',
        metavar='NAME',
        nargs='+',
        help='The resources to delete.')

  @abc.abstractproperty
  def resource_type(self):
    """The name of the collection that we will delete from."""

  @abc.abstractproperty
  def reference_creator(self):
    """A function that can construct resource reference objects."""

  @property
  def method(self):
    return 'Delete'

  def ScopeRequest(self, args, request):
    """Adds a zone or region to the request object if necessary."""

  @abc.abstractmethod
  def CreatePromptListItem(self, ref):
    pass

  def CreateRequests(self, args):
    """Returns a list of delete request protobufs."""
    delete_request_class = self.service.GetRequestType(self.method)
    name_field = self.service.GetMethodConfig(self.method).ordered_params[-1]

    refs = self.reference_creator(args.names, args)
    prompt_list = []
    for ref in refs:
      prompt_list.append(self.CreatePromptListItem(ref))

    prompt_message = utils.ConstructList(self.prompt_title, prompt_list)
    if not console_io.PromptContinue(message=prompt_message):
      raise calliope_exceptions.ToolException('Deletion aborted by user.')

    requests = []
    for ref in refs:
      request = delete_request_class(project=self.context['project'])
      setattr(request, name_field, ref.Name())
      self.ScopeRequest(ref, request)
      requests.append(request)
    return requests


class ZonalDeleter(BaseDeleter):
  """Base class for deleting zonal resources."""

  @staticmethod
  def Args(parser):
    BaseDeleter.Args(parser)
    utils.AddZoneFlag(
        parser, resource_type='resources', operation_type='delete')

  @property
  def reference_creator(self):
    return (lambda names, args: self.CreateZonalReferences(names, args.zone))

  def ScopeRequest(self, ref, request):
    request.zone = ref.zone

  def CreatePromptListItem(self, ref):
    return '[{0}] in [{1}]'.format(ref.Name(), ref.zone)

  def Run(self, args):
    self.prompt_title = 'The following {0} will be deleted:'.format(
        self.resource_type)
    return super(ZonalDeleter, self).Run(args)


class RegionalDeleter(BaseDeleter):
  """Base class for deleting regional resources."""

  @staticmethod
  def Args(parser):
    BaseDeleter.Args(parser)
    utils.AddRegionFlag(
        parser, resource_type='resources', operation_type='delete')

  @property
  def reference_creator(self):
    return (
        lambda names, args: self.CreateRegionalReferences(names, args.region))

  def ScopeRequest(self, ref, request):
    request.region = ref.region

  def CreatePromptListItem(self, ref):
    return '[{0}] in [{1}]'.format(ref.Name(), ref.region)

  def Run(self, args):
    self.prompt_title = 'The following {0} will be deleted:'.format(
        self.resource_type)
    return super(RegionalDeleter, self).Run(args)


class GlobalDeleter(BaseDeleter):
  """Base class for deleting global resources."""

  @property
  def reference_creator(self):
    return (lambda names, _: self.CreateGlobalReferences(names))

  def CreatePromptListItem(self, ref):
    return '[{0}]'.format(ref.Name())

  def Run(self, args):
    self.prompt_title = 'The following {0} will be deleted:'.format(
        self.resource_type)
    return super(GlobalDeleter, self).Run(args)


class ReadWriteCommand(BaseCommand):
  """Base class for read->update->write subcommands."""

  __metaclass__ = abc.ABCMeta

  @abc.abstractproperty
  def service(self):
    pass

  def CreateReference(self, args):
    """Returns a resources.Resource object for the object being mutated."""

  @abc.abstractmethod
  def GetGetRequest(self, args):
    """Returns a request for fetching the resource."""

  @abc.abstractmethod
  def GetSetRequest(self, args, replacement, existing):
    """Returns a request for setting the resource."""

  @abc.abstractmethod
  def Modify(self, args, existing):
    """Returns a modified resource."""

  def Run(self, args):
    self.ref = self.CreateReference(args)
    get_request = self.GetGetRequest(args)
    objects = list(request_helper.MakeRequests(
        requests=[get_request],
        http=self.context['http'],
        batch_url=self.context['batch-url']))

    new_object = self.Modify(args, objects[0])

    # If existing object is equal to the proposed object or if
    # Modify() returns None, then there is no work to be done, so we
    # print the resource and return.
    if not new_object or objects[0] == new_object:
      for resource in lister.ProcessResults(
          resources=[objects[0]],
          field_selector=property_selector.PropertySelector(
              properties=None,
              transformations=self.transformations)):
        yield resource
      return

    resources = request_helper.MakeRequests(
        requests=[self.GetSetRequest(args, new_object, objects[0])],
        http=self.context['http'],
        batch_url=self.context['batch-url'])

    resources = lister.ProcessResults(
        resources=resources,
        field_selector=property_selector.PropertySelector(
            properties=None,
            transformations=self.transformations))
    for resource in resources:
      yield resource

  def Display(self, _, resources):
    resource_printer.Print(
        resources=resources,
        print_format='yaml',
        out=log.out)


class BaseMetadataAdder(ReadWriteCommand):
  """Base class for adding or modifying metadata entries."""

  @staticmethod
  def Args(parser):
    metadata_utils.AddMetadataArgs(parser)

  def Modify(self, args, existing):
    new_object = copy.deepcopy(existing)
    existing_metadata = getattr(existing, self.metadata_field, None)
    setattr(
        new_object,
        self.metadata_field,
        metadata_utils.ConstructMetadataMessage(
            metadata=args.metadata,
            metadata_from_file=args.metadata_from_file,
            existing_metadata=existing_metadata))

    if metadata_utils.MetadataEqual(
        existing_metadata,
        getattr(new_object, self.metadata_field, None)):
      return None
    else:
      return new_object

  def Run(self, args):
    if not args.metadata and not args.metadata_from_file:
      raise calliope_exceptions.ToolException(
          'At least one of [--metadata] or [--metadata-from-file] must be '
          'provided.')

    return super(BaseMetadataAdder, self).Run(args)


class BaseMetadataRemover(ReadWriteCommand):
  """Base class for removing metadata entries."""

  @staticmethod
  def Args(parser):
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '--all',
        action='store_true',
        default=False,
        help='If provided, all metadata entries are removed.')
    group.add_argument(
        '--keys',
        help='The keys of the entries to remove.',
        metavar='KEY',
        nargs='+')

  def Modify(self, args, existing):
    new_object = copy.deepcopy(existing)
    existing_metadata = getattr(existing, self.metadata_field, None)
    setattr(new_object,
            self.metadata_field,
            metadata_utils.RemoveEntries(
                existing_metadata=existing_metadata,
                keys=args.keys,
                remove_all=args.all))

    if metadata_utils.MetadataEqual(
        existing_metadata,
        getattr(new_object, self.metadata_field, None)):
      return None
    else:
      return new_object

  def Run(self, args):
    if not args.all and not args.keys:
      raise calliope_exceptions.ToolException(
          'One of [--all] or [--keys] must be provided.')

    return super(BaseMetadataRemover, self).Run(args)


class InstanceMetadataMutatorMixin(ReadWriteCommand):
  """Mixin for mutating instance metadata."""

  @staticmethod
  def Args(parser):
    utils.AddZoneFlag(
        parser,
        resource_type='instance',
        operation_type='set metadata on')
    parser.add_argument(
        'name',
        metavar='NAME',
        help='The name of the instance whose metadata should be modified.')

  @property
  def resource_type(self):
    return 'instances'

  @property
  def service(self):
    return self.context['compute'].instances

  @property
  def metadata_field(self):
    return 'metadata'

  def CreateReference(self, args):
    return self.CreateZonalReference(args.name, args.zone)

  def GetGetRequest(self, args):
    return (self.service,
            'Get',
            messages.ComputeInstancesGetRequest(
                instance=self.ref.Name(),
                project=self.context['project'],
                zone=self.ref.zone))

  def GetSetRequest(self, args, replacement, existing):
    return (self.service,
            'SetMetadata',
            messages.ComputeInstancesSetMetadataRequest(
                instance=self.ref.Name(),
                metadata=replacement.metadata,
                project=self.context['project'],
                zone=self.ref.zone))


class InstanceTagsMutatorMixin(ReadWriteCommand):
  """Mixin for mutating instance tags."""

  @staticmethod
  def Args(parser):
    utils.AddZoneFlag(
        parser,
        resource_type='instance',
        operation_type='set tags on')
    parser.add_argument(
        'name',
        metavar='NAME',
        help='The name of the instance whose tags should be modified.')

  @property
  def resource_type(self):
    return 'instances'

  @property
  def service(self):
    return self.context['compute'].instances

  def CreateReference(self, args):
    return self.CreateZonalReference(args.name, args.zone)

  def GetGetRequest(self, args):
    return (self.service,
            'Get',
            messages.ComputeInstancesGetRequest(
                instance=self.ref.Name(),
                project=self.context['project'],
                zone=self.ref.zone))

  def GetSetRequest(self, args, replacement, existing):
    return (self.service,
            'SetTags',
            messages.ComputeInstancesSetTagsRequest(
                instance=self.ref.Name(),
                tags=replacement.tags,
                project=self.context['project'],
                zone=self.ref.zone))


class ProjectMetadataMutatorMixin(ReadWriteCommand):
  """Mixin for mutating project-level metadata."""

  @property
  def service(self):
    return self.context['compute'].projects

  @property
  def metadata_field(self):
    return 'commonInstanceMetadata'

  def GetGetRequest(self, args):
    return (self.service,
            'Get',
            messages.ComputeProjectsGetRequest(
                project=self.context['project']))

  def GetSetRequest(self, args, replacement, existing):
    return (self.service,
            'SetCommonInstanceMetadata',
            messages.ComputeProjectsSetCommonInstanceMetadataRequest(
                metadata=replacement.commonInstanceMetadata,
                project=self.context['project']))


_HELP = textwrap.dedent("""\
    You can edit the resource below. Lines beginning with "#" are
    ignored.

    If you introduce a syntactic error, you will be given the
    opportunity to edit the file again. You can abort by closing this
    file without saving it.

    At the bottom of this file, you will find an example resource.

    Only fields that can be modified are shown. The original resource
    with all of its fields is reproduced in the comment section at the
    bottom of this document.
    """)


def _SerializeDict(value, fmt):
  """Serializes value to either JSON or YAML."""
  if fmt == 'json':
    return json.dumps(
        value,
        indent=2,
        sort_keys=True,
        separators=(',', ': '))
  else:
    yaml.add_representer(
        collections.OrderedDict,
        yaml.dumper.SafeRepresenter.represent_dict,
        Dumper=yaml.dumper.SafeDumper)
    return yaml.safe_dump(
        value,
        indent=2,
        default_flow_style=False,
        width=70)


def _DeserializeValue(value, fmt):
  """Parses the given JSON or YAML value."""
  if fmt == 'json':
    return json.loads(value)
  else:
    return yaml.load(value)


def _WriteResourceInCommentBlock(serialized_resource, title, buf):
  """Outputs a comment block with the given serialized resource."""
  buf.write('# ')
  buf.write(title)
  buf.write('\n# ')
  buf.write('-' * len(title))
  buf.write('\n#\n')
  for line in serialized_resource.splitlines():
    buf.write('#')
    if line:
      buf.write('   ')
      buf.write(line)
      buf.write('\n')


class BaseEdit(BaseCommand):
  """Base class for modifying resources using $EDITOR."""

  __metaclass__ = abc.ABCMeta

  DEFAULT_FORMAT = 'yaml'

  @abc.abstractproperty
  def service(self):
    pass

  @abc.abstractmethod
  def GetGetRequest(self, args):
    """Returns a request for fetching the resource."""

  @abc.abstractmethod
  def GetSetRequest(self, args, replacement, existing):
    """Returns a request for setting the resource."""

  @abc.abstractproperty
  def example_resource(self):
    pass

  def ProcessEditedResource(self, file_contents, args):
    """Returns an updated resource that was edited by the user."""

    # It's very important that we replace the characters of comment
    # lines with spaces instead of removing the comment lines
    # entirely. JSON and YAML deserialization give error messages
    # containing line, column, and the character offset of where the
    # error occurred. If the deserialization fails; we want to make
    # sure those numbers map back to what the user actually had in
    # front of him or her otherwise the errors will not be very
    # useful.
    non_comment_lines = '\n'.join(
        ' ' * len(line) if line.startswith('#') else line
        for line in file_contents.splitlines())

    modified_record = _DeserializeValue(non_comment_lines,
                                        args.format or BaseEdit.DEFAULT_FORMAT)

    if self.modifiable_record == modified_record:
      new_object = None

    else:
      modified_record['name'] = self.original_record['name']
      fingerprint = self.original_record.get('fingerprint')
      if fingerprint:
        modified_record['fingerprint'] = fingerprint

      new_object = encoding.DictToMessage(
          modified_record, self._resource_spec.message_class)

    # If existing object is equal to the proposed object or if
    # there is no new object, then there is no work to be done, so we
    # return the original object.
    if not new_object or self.original_object == new_object:
      return [self.original_object]

    resources = list(request_helper.MakeRequests(
        requests=[self.GetSetRequest(args, new_object, self.original_object)],
        http=self.context['http'],
        batch_url=self.context['batch-url']))

    return resources

  def Run(self, args):
    get_request = self.GetGetRequest(args)
    objects = list(request_helper.MakeRequests(
        requests=[get_request],
        http=self.context['http'],
        batch_url=self.context['batch-url']))

    self.original_object = objects[0]
    self.original_record = encoding.MessageToDict(self.original_object)

    # Selects only the fields that can be modified.
    field_selector = property_selector.PropertySelector(
        properties=self._resource_spec.editables)
    self.modifiable_record = field_selector.Apply(self.original_record)

    buf = cStringIO.StringIO()
    for line in _HELP.splitlines():
      buf.write('#')
      if line:
        buf.write(' ')
      buf.write(line)
      buf.write('\n')

    buf.write('\n')
    buf.write(_SerializeDict(self.modifiable_record,
                             args.format or BaseEdit.DEFAULT_FORMAT))
    buf.write('\n')

    example = _SerializeDict(
        encoding.MessageToDict(self.example_resource),
        args.format or BaseEdit.DEFAULT_FORMAT)
    _WriteResourceInCommentBlock(example, 'Example resource:', buf)

    buf.write('#\n')

    original = _SerializeDict(self.original_record,
                              args.format or BaseEdit.DEFAULT_FORMAT)
    _WriteResourceInCommentBlock(original, 'Original resource:', buf)

    file_contents = buf.getvalue()
    while True:
      file_contents = edit.OnlineEdit(file_contents)
      try:
        resources = self.ProcessEditedResource(file_contents, args)
        break
      except (ValueError, yaml.error.YAMLError,
              protorpc.messages.ValidationError,
              calliope_exceptions.ToolException) as e:
        if isinstance(e, ValueError):
          message = e.message
        else:
          message = str(e)

        if isinstance(e, calliope_exceptions.ToolException):
          problem_type = 'applying'
        else:
          problem_type = 'parsing'

        message = ('There was a problem {0} your changes: {1}'
                   .format(problem_type, message))
        if not console_io.PromptContinue(
            message=message,
            prompt_string='Would you like to edit the resource again?'):
          raise calliope_exceptions.ToolException('Edit aborted by user.')

    resources = lister.ProcessResults(
        resources=resources,
        field_selector=property_selector.PropertySelector(
            properties=None,
            transformations=self.transformations))
    for resource in resources:
      yield resource

  def Display(self, _, resources):
    resource_printer.Print(
        resources=resources,
        print_format='yaml',
        out=log.out)
