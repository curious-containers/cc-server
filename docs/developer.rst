Developer Documentation
=======================

This page contains developer documentation. It is advised to read through the administrator and user documentation first.

Contributing
------------

If you find a bug or would like to request a feature, please file an
`issue on Github <https://github.com/curious-containers/cc-server/issues>`__. If you implemented a bug fix, please create a
`pull request <https://github.com/curious-containers/cc-server/pulls>`__. Pull requests for features should be discussed
first.

Building the Documentation
--------------------------

Install additional Python3 packages:

.. code-block:: bash

   pip3 install --user --upgrade flask sphinx sphinx-autobuild sphinxcontrib-httpdomain sphinx_rtd_theme bibtex-pygments-lexer


Run *make* inside the docs-src directory:

.. code-block:: bash

   cd docs
   make html

