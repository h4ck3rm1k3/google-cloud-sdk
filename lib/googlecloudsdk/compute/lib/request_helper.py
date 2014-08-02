# Copyright 2014 Google Inc. All Rights Reserved.
"""Module for making API requests."""

from googlecloudsdk.compute.lib import batch_helper
from googlecloudsdk.compute.lib import utils
from googlecloudsdk.compute.lib import waiters
from googlecloudsdk.core import log


def MakeRequests(requests, http, batch_url, custom_get_requests=None):
  """Makes one or more requests to the API.

  Each request can be either a synchronous API call or an asynchronous
  one. For synchronous calls (e.g., get and list), the result from the
  server is yielded immediately. For asynchronous calls (e.g., calls
  that return operations like insert), this function waits until the
  operation reaches the DONE state and fetches the corresponding
  object and yields that object (nothing is yielded for deletions).

  Currently, a heterogenous set of synchronous calls can be made
  (e.g., get request to fetch a disk and instance), however, the
  asynchronous requests must be homogenous (e.g., they must all be the
  same verb on the same collection). In the future, heterogenous
  asynchronous requests will be supported. For now, it is up to the
  client to ensure that the asynchronous requests are
  homogenous. Synchronous and asynchronous requests can be mixed.

  Args:
    requests: A list of requests to make. Each element must be a 3-element
      tuple where the first element is the service, the second element is
      the string name of the method on the service, and the last element
      is a protocol buffer representing the request.
    http: An httplib2.Http-like object.
    batch_url: The handler for making batch requests.
    custom_get_requests: A mapping of resource names to requests. If
      this is provided, when an operation is DONE, instead of performing
      a get on the targetLink, this function will consult custom_get_requests
      and perform the request dictated by custom_get_requests.

  Yields:
    A response for each request. For deletion requests, no corresponding
    responses are returned.
  """
  responses, errors = batch_helper.MakeRequests(
      requests=requests, http=http, batch_url=batch_url)

  operation_service = None
  resource_service = None
  project = None

  # Collects all operation objects in a list so they can be waited on
  # and yields all non-operation objects since non-operation responses
  # cannot be waited on.
  operations = []
  for request, response in zip(requests, responses):
    if response is None:
      continue

    service, _, request_body = request
    if isinstance(response, service.client.MESSAGES_MODULE.Operation):
      operations.append(response)

      if not operation_service:
        resource_service = service
        project = request_body.project

        if response.zone:
          operation_service = service.client.zoneOperations
        elif response.region:
          operation_service = service.client.regionOperations
        else:
          operation_service = service.client.globalOperations

    else:
      yield response

  if operations:
    warnings = []
    for response in waiters.WaitForOperations(
        operations=operations,
        project=project,
        operation_service=operation_service,
        resource_service=resource_service,
        http=http,
        batch_url=batch_url,
        custom_get_requests=custom_get_requests,
        warnings=warnings or [],
        errors=errors):
      yield response

    if warnings:
      log.warn(utils.ConstructList('Some requests generated warnings:',
                                   warnings))

  if errors:
    utils.RaiseToolException(errors)
