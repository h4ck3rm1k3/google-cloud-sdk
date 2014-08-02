# Copyright 2014 Google Inc. All Rights Reserved.
"""Common classes and functions for images."""
from googlecloudapis.compute.v1 import compute_v1_messages as messages
from googlecloudsdk.calliope import exceptions
from googlecloudsdk.compute.lib import constants
from googlecloudsdk.compute.lib import lister
from googlecloudsdk.core import log
from googlecloudsdk.core.util import console_io


class ImageResourceFetcher(object):
  """Mixin class for displaying images."""

  def GetResources(self, args, errors):
    """Yields images from (potentially) multiple projects."""
    filter_expression = lister.ConstructNameFilterExpression(args.name_regex)

    requests = [
        (self.service,
         messages.ComputeImagesListRequest(
             filter=filter_expression,
             maxResults=constants.MAX_RESULTS_PER_PAGE,
             project=self.context['project'])),
    ]

    if not args.no_standard_images:
      for project in constants.IMAGE_PROJECTS:
        requests.append(
            (self.service,
             messages.ComputeImagesListRequest(
                 filter=filter_expression,
                 maxResults=constants.MAX_RESULTS_PER_PAGE,
                 project=project)))

    images = lister.BatchList(
        requests=requests,
        http=self.context['http'],
        batch_url=self.context['batch-url'],
        errors=errors)

    for image in images:
      if not image.deprecated or args.show_deprecated:
        yield image


class ImageExpander(object):
  """Mixin class for expanding image aliases."""

  def GetMatchingImages(self, image, alias):
    """Yields images from a public image project and the user's project."""
    service = self.context['compute'].images
    requests = [
        (service,
         messages.ComputeImagesListRequest(
             filter=lister.ConstructNameFilterExpression(
                 ['^{0}-v[0-9]+.*'.format(alias.name_prefix)]),
             maxResults=constants.MAX_RESULTS_PER_PAGE,
             project=alias.project)),
        (service,
         messages.ComputeImagesListRequest(
             filter=lister.ConstructNameFilterExpression(
                 ['^{0}$'.format(image)]),
             maxResults=constants.MAX_RESULTS_PER_PAGE,
             project=self.context['project'])),
    ]

    return lister.BatchList(
        requests=requests,
        http=self.context['http'],
        batch_url=self.context['batch-url'],

        errors=[])

  def ExpandImageFlag(self, args):
    """Returns a full URI for the given value of --image."""
    image_flag_value = args.image or constants.DEFAULT_IMAGE

    # If an image project was specified, then assume that image refers
    # to an image in that project.
    if args.image_project:
      return self.context['uri-builder'].Build(
          'global', 'images', image_flag_value, project=args.image_project)

    alias = constants.IMAGE_ALIASES.get(image_flag_value)

    # If the image name given is not an alias and no image project was
    # provided, then assume that the image value refers to an image in
    # the user's project.
    if not alias:
      return self.context['uri-builder'].Build(
          'global', 'images', image_flag_value)

    # At this point, the image is an alias and now we have to find the
    # latest one among the public image project and the user's
    # project.

    images = self.GetMatchingImages(image_flag_value, alias)

    user_image = None
    public_images = []

    for image in images:
      if image.deprecated:
        continue
      if '/projects/{0}/'.format(self.context['project']) in image.selfLink:
        user_image = image
      else:
        public_images.append(image)

    if not public_images:
      raise exceptions.ToolException(
          'No image was found for alias [{0}] in public image project [{1}]. '
          'Try specifying a different image using [--image].'
          .format(image_flag_value, alias.project))

    public_candidate = max(public_images, key=lambda x: x.name)
    if user_image:
      self_links = [user_image.selfLink, public_candidate.selfLink]

      idx = console_io.PromptChoice(
          options=self_links,
          default=0,
          message=('Found two possible choices for [--image] value [{0}].'
                   .format(image_flag_value)))

      res = self_links[idx]

    else:
      res = public_candidate.selfLink

    log.debug('Image resolved to [%s].', res)
    return res


def AddImageFetchingArgs(parser):
  """Adds common flags for getting and listing images."""
  parser.add_argument(
      '--show-deprecated',
      action='store_true',
      help='If provided, deprecated images are shown.')

  no_standard_images = parser.add_argument(
      '--no-standard-images',
      action='store_true',
      help='If provided, images from well-known image projects are not shown.')
  no_standard_images.detailed_help = """\
     If provided, images from well-known image projects are not
     shown. The well known image projects are: {0}.
     """.format(', '.join(constants.IMAGE_PROJECTS))


def AddImageProjectFlag(parser):
  """Adds the --image flag to the given parser."""
  image_project = parser.add_argument(
      '--image-project',
      help='The project against which all image references will be resolved.')
  image_project.detailed_help = """\
      The project against which all image references will be
      resolved. See ``--image'' for more details.
      """


def GetImageAliasTable():
  """Returns help text that explains the image aliases."""
  # Note: The leading spaces are very important in this string. The
  # final help text is dedented, so if the leading spaces are off, the
  # help will not be generated properly.
  return """The value for this option can be the name of an image or an
          alias from the table below.
          +
          [options="header",format="csv",grid="none",frame="none"]
          |========
          Alias,Project,Image Name,
          {0}
          |========
          +
          When the value is an alias, this tool will query the public
          image project that contains the image type to find the
          latest image matching the alias. The user's project is also
          queried for an image with the same name as the alias. If a
          conflict exists, the user will be prompted to resolve the
          conflict.
          +
          To specify an image in another project for which there is no
          alias, use ``--image-project''. When ``--image-project'' is
          present, no API calls are made to resolve the image. This
          property is useful for scripts.""".format(
              '\n          '.join(
                  ','.join([alias, project, image_name])
                  for alias, (project, image_name) in
                  sorted(constants.IMAGE_ALIASES.iteritems())))
