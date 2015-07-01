# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import logging
import os
import pwd

from pants.base.build_environment import get_buildroot
from pants.scm.git import Git


logger = logging.getLogger(__file__)

class SquareManifest:
  """Provides additional fields to MANIFEST.MF."""

  def __init__(self, parse_context):
    """
    :param ParseContext parse_context: build file context
    """
    self._parse_context = parse_context

  def __call__(self, manifest_entries=None):
    """Returns a dict suitable for passing to 'manifest_entries' in a 'jvm_binary() definition"""
    manifest_entries = manifest_entries or {}
    buildroot = get_buildroot()
    worktree = Git.detect_worktree(subdir=os.path.join(buildroot,
                                                    self._parse_context.rel_path))
    if worktree:
      git = Git(worktree=worktree)
      manifest_entries['Implementation-Version'] = git.commit_id
    manifest_entries['Built-By'] = pwd.getpwuid(os.getuid()).pw_name
    return manifest_entries


