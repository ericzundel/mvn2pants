From the root of the repo, run all of these tests with

  ./pants goal test squarepants:test

which is just a shortcut for:

  ./pants goal test squarepants/src/test/python/squarepants



Run individual tests with an individual target as follows:

  ./pants goal test squarepants/src/test/python/squarepants:pom_handlers
