This directory contains some custom Pants plugins we use at Square.
See http://pantsbuild.github.io for more information about plugins

Install these plugins into pants.ini as follows:

[backends]
packages: [
    "squarepants.plugins.square_maven_layout", 
    "squarepants.plugins.sjar",
  ]
