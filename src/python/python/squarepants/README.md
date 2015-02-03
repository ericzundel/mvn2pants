Scripts Square uses to convert maven pom.xml files into BUILD files.

Notes: Assumes the root pom.xml file contains project definitions.
       Assumes that a single parents/base/pom.xml contains dependencyManagement definitions.

regenerate_all.py: regenerates all the BUILD.gen and BUILD.aux files from pom.xml files 
check_pex_health.py: checks the fingerprint of the current pex against a previously cached one.

zundel@squareup.com
