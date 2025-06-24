This folder contains the source code and Manual of the CGLRRM model. Which is developed using Fortran.
It is suggested to compile the code in Windows following the instruction

It is suggested to compile the CGLRRM Fortran code in Windows and generate the .exe file.

Software installation:
(1)	MS-Visual Studio 
(it is necessary to install the Desktop development with C++ component from Visual Studio.)

https://visualstudio.microsoft.com/ 

https://www.intel.com/content/www/us/en/developer/articles/guide/installing-microsoft-visual-studio-2019-for-use-with-intel-compilers.html

(2)	Intel oneAPI base tool (https://www.intel.com/content/www/us/en/developer/tools/oneapi/toolkits.html#gs.6bmll)

(3)	Intel oneAPI HPC,

https://www.intel.com/content/www/us/en/developer/articles/training/intel-fortran-compiler-in-ms-visual-studio.html

(4)	Compile
https://www.intel.com/content/www/us/en/docs/fortran-compiler/get-started-guide/2022-2/get-started-on-windows.html#GUID-6909EF81-DBD6-42B7-AFEC-0FB9BD1BB268

-	open Intel OneAPI command prompt
-	go to the source code directory: “cd ….’
-	Compile: “ifort -o (.exe path and name) (all the .for source code)”.
Example: ifort -o cglrrm_test CALCUTL.FOR CGLRRM.FOR CONTROL.FOR CUSTOM.FOR INIT.FOR MIDLAKES.FOR MISCUTL.FOR ontario.for ontarioinit.for Preproject.for SUPERIOR.FOR SuperiorRegPlans.for TSINPUT.FOR

