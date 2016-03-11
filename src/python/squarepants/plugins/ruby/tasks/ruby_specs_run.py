# coding=utf-8
# Copyright 2015 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).
import subprocess, os

from pants.task.task import Task
from pants.base.exceptions import TaskError

from squarepants.plugins.ruby.targets.ruby_specs import RubySpecs

class RubySpecsRun(Task):
  def execute(self):
    """runs ruby specs for ruby targets with necessary setup beforehand"""
    targets = self.context.targets()
    ruby_spec_targets = [target for target in targets if isinstance(target, RubySpecs)]

    if ruby_spec_targets:
      for target in targets:
        self.bundle_setup(target.payload.cwd)
        self.run_specs(target)

  def run_specs(self, target):
    """runs ruby spec by shelling out and calling `rspec` command"""
    spec_files = target.sources_relative_to_buildroot()
    cwd = target.payload.cwd
    specs = [os.path.abspath(file.encode("UTF-8")) for file in spec_files]
    exitcode, out, err = self.bundle_exec_rspec(specs, cwd)
    if exitcode != 0:
      self.context.log.error(out)
      raise TaskError
    else:
      output_lines = out.splitlines()
      message = '\n'.join(output_lines[len(output_lines)-3:len(output_lines)-1])
      self.context.log.info(message)

  def bundle_setup(self, cwd):
    """run bundle check & setup"""
    self.context.log.info("Bundler setup")
    bundle_check, bundle_check_out = self.bundle_check(cwd)
    if not bundle_check:
      self.context.log.warn(bundle_check_out)
      self.bundle_install(cwd)

  def bundle_check(self, cwd):
    """check if gems are bundled, this is faster than `bundle install`
       which tries to install whole bundle even if it's already installed"""
    self.context.log.info("Checking if bundle is installed")
    # The sample stdout returned by `bundle check`:
    #
    #  The following gems are missing
    #   * squab-client (1.4.2)
    #  Install missing gems with `bundle install`
    exitcode, out, _ = self.exec_cmd("bundle check", cwd)
    return exitcode == 0, out

  def bundle_install(self, cwd):
    """run bundle install"""
    # TODO: This assumes that the Gemfile is in the same
    # directory in which command is executed. We may want to
    # make it configurable and by setting path to Gemfile in
    # `BUNDLE_GEMFILE` env var.
    self.context.log.info("Running bundle install")
    return self.exec_cmd("bundle install", cwd)

  def bundle_exec_rspec(self, spec_list, cwd):
    """run rspecs for given spec files
    :param spec_list: list of spec files to run
    :param cwd: directory to change to inf not None
    """
    self.context.log.info("Running specs")
    return self.exec_cmd("bundle exec rspec {specs}".format(specs=' '.join(spec_list)))

  def exec_cmd(self, cmd, cwd=None):
    """convinence wrapper for Popen"""
    self.context.log.debug("Running shell command: ", str(cmd))
    proc = subprocess.Popen([cmd], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
    out, err = proc.communicate()
    exitcode = proc.returncode
    self.context.log.debug("command finished with {exitcode} code\n stdout: {stdout}\n\nstderr: {stderr}".format(exitcode=str(exitcode), stdout=out, stderr=err))
    return exitcode, out, err
