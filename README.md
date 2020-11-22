# November 22, 2020

Although this code hasn't been touched in a long time, I was doing some cleaning
in my github repo and saw that this batch of code was sitting around with no 
explaination.  -Eric.

# Squarepants BUILD file generation tool (or mvn2pants)

This project is an extraction of a tool used at Square circa 2017 to 
automatically generate BUILD files from Maven pom.xml files.  There were 
several contributors at Square to this codebase.

The "squarepants" tool was integrated into the Square monorepo when it was 
still primarily running Maven that allowed users to try pants, and for me to 
start generating builds and testing them out. This subset of the tool was uploaded as an example for others in the 
Pants community who expressed interest in building a tool of their own.  
It is not a usable product in this state and does not run out of the box.  
It is likely far out of date with Pants 2.0.


The useful parts of this codebase are the parts that parse the pom.xml files, 
understand the dependencies between projects, and translate parts of the 
pom.xml into BUILD file constructs.  The Square repo had a sophisticated use of Maven that tied together versions from many projects into common settings which
we used to generate a 3rdparty/BUILD file.  It also had a somewhat complex
generation of proto definitions that were pulled in from a .jar file collected from many repos (external-protos/).
