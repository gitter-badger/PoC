# EMACS settings: -*-	tab-width: 2; indent-tabs-mode: t -*-
# vim: tabstop=2:shiftwidth=2:noexpandtab
# kate: tab-width 2; replace-tabs off; indent-width 2;
# 
# ==============================================================================
# Authors:				 	Patrick Lehmann
# 
# Python Class:			TODO
# 
# Description:
# ------------------------------------
#		TODO:
#		- 
#		- 
#
# License:
# ==============================================================================
# Copyright 2007-2015 Technische Universitaet Dresden - Germany
#											Chair for VLSI-Design, Diagnostics and Architecture
# 
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
# 
#		http://www.apache.org/licenses/LICENSE-2.0
# 
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
#
# entry point
if __name__ != "__main__":
	# place library initialization code here
	pass
else:
	from lib.Functions import Exit
	Exit.printThisIsNoExecutableFile("The PoC-Library - Python Module Simulator.VivadoSimulator")

# load dependencies
from pathlib import Path

from Base.Exceptions import *
from Simulator.Base import PoCSimulator 
from Simulator.Exceptions import *


class Simulator(PoCSimulator):

	__executables =			{}
	__vhdlStandard =		"93"
	__guiMode =					False

	def __init__(self, host, showLogs, showReport, guiMode):
		super(self.__class__, self).__init__(host, showLogs, showReport)

		self.__guiMode =					guiMode

		if (host.platform == "Windows"):
			self.__executables['xElab'] =		"xelab.bat"
			self.__executables['xSim'] =		"xsim.bat"
		elif (host.platform == "Linux"):
			self.__executables['xElab'] =		"xelab"
			self.__executables['xSim'] =		"xsim"
		else:
			raise PlatformNotSupportedException(self.platform)
		
	def run(self, pocEntity):
		import os
		import re
		import subprocess
	
		self.printNonQuiet(str(pocEntity))
		self.printNonQuiet("  preparing simulation environment...")
		
		
		# create temporary directory for xSim if not existent
		tempXSimPath = self.host.directories["xSimTemp"]
		if not (tempXSimPath).exists():
			self.printVerbose("Creating temporary directory for simulator files.")
			self.printDebug("Temporary directors: %s" % str(tempXSimPath))
			tempXSimPath.mkdir(parents=True)

		# setup all needed paths to execute elab
		#vhpcompExecutablePath =	self.host.directories["VivadoBinary"] / self.__executables['vhpcomp']
		xelabExecutablePath =		self.host.directories["VivadoBinary"] / self.__executables['xElab']
		xSimExecutablePath =		self.host.directories["VivadoBinary"] / self.__executables['xSim']
		
		if not self.host.tbConfig.has_section(str(pocEntity)):
			from configparser import NoSectionError
			raise SimulatorException("Testbench '" + str(pocEntity) + "' not found.") from NoSectionError(str(pocEntity))
		
		testbenchName =			self.host.tbConfig[str(pocEntity)]['TestbenchModule']
		fileListFilePath =	self.host.directories["PoCRoot"] / self.host.tbConfig[str(pocEntity)]['fileListFile']
		tclBatchFilePath =	self.host.directories["PoCRoot"] / self.host.tbConfig[str(pocEntity)]['xSimBatchScript']
		tclGUIFilePath =		self.host.directories["PoCRoot"] / self.host.tbConfig[str(pocEntity)]['xSimGUIScript']
		wcfgFilePath =			self.host.directories["PoCRoot"] / self.host.tbConfig[str(pocEntity)]['xSimWaveformConfigFile']
		prjFilePath =				tempXSimPath / (testbenchName + ".prj")
		xelabLogFilePath =	tempXSimPath / (testbenchName + ".xelab.log")
		xSimLogFilePath =		tempXSimPath / (testbenchName + ".xsim.log")
		snapshotName =			testbenchName

		# report the next steps in execution
#		if (self.getVerbose()):
#			print("  Commands to be run:")
#			print("  1. Change working directory to temporary directory.")
#			print("  2. Parse filelist and write xSim project file.")
#			print("  3. Compile and Link source files to an executable simulation file.")
#			print("  4. Simulate in tcl batch mode.")
#			print("  ----------------------------------------")
		
		# change working directory to temporary xSim path
		self.printVerbose('  cd "%s"' % str(tempXSimPath))
		os.chdir(str(tempXSimPath))

		# parse project filelist
		filesLineRegExpStr =	r"^"																						#	start of line
		filesLineRegExpStr =	r"(?:"																					#	open line type: empty, directive, keyword
		filesLineRegExpStr +=		r"(?P<EmptyLine>)|"														#		empty line
		filesLineRegExpStr +=		r"(?P<Directive>"															#		open directives:
		filesLineRegExpStr +=			r"(?P<DirInclude>@include)|"								#			 @include
		filesLineRegExpStr +=			r"(?P<DirLibrary>@library)"									#			 @library
		filesLineRegExpStr +=		r")|"																					#		close directives
		filesLineRegExpStr +=		r"(?P<Keyword>"																#		open keywords:
		filesLineRegExpStr +=			r"(?P<KwAltera>altera)|"										#			altera
		filesLineRegExpStr +=			r"(?P<KwXilinx>xilinx)|"										#			xilinx
		filesLineRegExpStr +=			r"(?P<KwVHDL>vhdl"													#			vhdl[-nn]
		filesLineRegExpStr +=				r"(?:-(?P<VHDLStandard>87|93|02|08))?)"		#				VHDL Standard Year: [-nn]
		filesLineRegExpStr +=		r")"																					#		close keywords
		filesLineRegExpStr +=	r")"																						#	close line type
		filesLineRegExpStr +=	r"(?(Directive)\s+(?:"													#	open directive parameters
		filesLineRegExpStr +=		r"(?(DirInclude)"															#		open @include directive
		filesLineRegExpStr +=			r"\"(?P<IncludeFile>.*?\.files)\""					#			*.files filename without enclosing "-signs
		filesLineRegExpStr +=		r")|"																					#		close @include directive
		filesLineRegExpStr +=		r"(?(DirLibrary)"															#		open @include directive
		filesLineRegExpStr +=			r"(?P<LibraryName>[_a-zA-Z0-9]+)"						#			VHDL library name
		filesLineRegExpStr +=			r"\s+"																			#			delimiter
		filesLineRegExpStr +=			r"\"(?P<LibraryPath>.*?)\""									#			VHDL library path without enclosing "-signs
		filesLineRegExpStr +=		r")"																					#		close @library directive
		filesLineRegExpStr +=	r"))"																						#	close directive parameters
		filesLineRegExpStr +=	r"(?(Keyword)\s+(?:"														#	open keyword parameters
		filesLineRegExpStr +=		r"(?P<VHDLLibrary>[_a-zA-Z0-9]+)"							#		VHDL library name
		filesLineRegExpStr +=		r"\s+"																				#		delimiter
		filesLineRegExpStr +=		r"\"(?P<VHDLFile>.*?\.vhdl?)\""								#		*.vhdl? filename without enclosing "-signs
		filesLineRegExpStr +=	r"))"																						#	close keyword parameters
		filesLineRegExpStr +=	r"\s*(?P<Comment>#.*)?"													#	optional comment until line end
		filesLineRegExpStr +=	r"$"																						#	end of line
		filesLineRegExp = re.compile(filesLineRegExpStr)

		self.printDebug("Reading filelist '%s'" % str(fileListFilePath))
		xSimProjectFileContent = ""
		externalLibraries = []
		with fileListFilePath.open('r') as prjFileHandle:
			for line in prjFileHandle:
				filesLineRegExpMatch = filesLineRegExp.match(line)
		
				if (filesLineRegExpMatch is not None):
					if (filesLineRegExpMatch.group('Directive') is not None):
						if (filesLineRegExpMatch.group('DirInclude') is not None):
							includeFile = filesLineRegExpMatch.group('IncludeFile')
							self.printVerbose("    referencing another file: {0}".format(includeFile))
						elif (filesLineRegExpMatch.group('DirLibrary') is not None):
							externalLibraryName = filesLineRegExpMatch.group('LibraryName')
							externalLibraryPath = filesLineRegExpMatch.group('LibraryPath')
							
							self.printVerbose("    referencing precompiled VHDL library: {0}".format(externalLibraryName))
							externalLibraries.append(externalLibraryPath)
						else:
							raise SimulatorException("Unknown directive in *.files file.")
						
						continue
						
					elif (filesLineRegExpMatch.group('Keyword') is not None):
						if (filesLineRegExpMatch.group('Keyword') == "vhdl"):
							vhdlFileName = filesLineRegExpMatch.group('VHDLFile')
							vhdlFilePath = self.host.directories["PoCRoot"] / vhdlFileName
						elif (filesLineRegExpMatch.group('Keyword')[0:5] == "vhdl-"):
							if (filesLineRegExpMatch.group('Keyword')[-2:] == self.__vhdlStandard):
								vhdlFileName = filesLineRegExpMatch.group('VHDLFile')
								vhdlFilePath = self.host.directories["PoCRoot"] / vhdlFileName
							else:
								continue
						elif (filesLineRegExpMatch.group('Keyword') == "altera"):
							self.printVerbose("    skipped Altera specific file: '%s'" % filesLineRegExpMatch.group('VHDLFile'))
							# vhdlFileName = filesLineRegExpMatch.group('VHDLFile')
							# vhdlFilePath = self.host.directories["XilinxPrimitiveSource"] / vhdlFileName
						elif (filesLineRegExpMatch.group('Keyword') == "xilinx"):
							self.printVerbose("    skipped Xilinx specific file: '%s'" % filesLineRegExpMatch.group('VHDLFile'))
							# vhdlFileName = filesLineRegExpMatch.group('VHDLFile')
							# vhdlFilePath = self.host.directories["XilinxPrimitiveSource"] / vhdlFileName
						else:
							raise SimulatorException("Unknown keyword in *files file.")
					
						vhdlLibraryName = filesLineRegExpMatch.group('VHDLLibrary')
						xSimProjectFileContent += "vhdl %s \"%s\"\n" % (vhdlLibraryName, str(vhdlFilePath))
						
						if (not vhdlFilePath.exists()):
							raise SimulatorException("Can not add '" + vhdlFileName + "' to project file.") from FileNotFoundError(str(vhdlFilePath))
		
		# write xSim project file
		self.printDebug("Writing xSim project file to '%s'" % str(prjFilePath))
		with prjFilePath.open('w') as prjFileHandle:
			prjFileHandle.write(xSimProjectFileContent)


		# running elab
		# ==========================================================================
		self.printNonQuiet("  running xelab...")
		# assemble xelab command as list of parameters
		parameterList = [
			str(xelabExecutablePath),
			'--prj',	str(prjFilePath),
			'--log',	str(xelabLogFilePath),
			'--timeprecision_vhdl', '1fs',			# set minimum time precision to 1 fs
			'--mt', '4',												# enable multithread support
			'--O2',
			'--debug', 'typical',
			'--snapshot',	snapshotName,
			'--rangecheck'
		]
		
		# append debug options
		if (self.verbose):
			parameterList += [
				'--verbose', '0']

		# append testbench name
		parameterList += [('test.%s' % testbenchName)]
		
		command = " ".join(parameterList)
		
		self.printDebug("call xelab: %s" % str(parameterList))
		self.printVerbose("    command: %s" % command)
		
		try:
			linkerLog = subprocess.check_output(parameterList, stderr=subprocess.STDOUT, universal_newlines=True)
		except subprocess.CalledProcessError as ex:
			print("ERROR while executing xelab: %s" % str(vhdlFilePath))
			print("Return Code: %i" % ex.returncode)
			print("-" * 80)
			print(ex.output)
			print("-" * 80)
			
			return
		
		if self.showLogs:
			print("xelab log (xelab)")
			print("--------------------------------------------------------------------------------")
			print(linkerLog)
			print()
		
		# running simulation
		self.printNonQuiet("  running simulation...")
		parameterList = [
			str(xSimExecutablePath),
			'--log', str(xSimLogFilePath)
		]
		
		if (not self.__guiMode):
			parameterList += ['-tclbatch', str(tclBatchFilePath)]
		else:
			parameterList += [
				'-tclbatch', str(tclGUIFilePath),
				'-gui'
			]
			# if waveform configuration file exists, load it's settings
			if wcfgFilePath.exists():
				parameterList += ['--view', str(wcfgFilePath)]
		
		# append testbench name
		parameterList += [
			snapshotName
		]
		
		command = " ".join(parameterList)
		
		self.printDebug("call simulation: %s" % str(parameterList))
		self.printVerbose("    command: %s" % command)
		
		try:
			simulatorLog = subprocess.check_output(parameterList, stderr=subprocess.STDOUT, universal_newlines=True)
		except subprocess.CalledProcessError as ex:
			print("ERROR while executing xSim: %s" % str(vhdlFilePath))
			print("Return Code: %i" % ex.returncode)
			print("-" * 80)
			print(ex.output)
			print("-" * 80)
			
			return
		
		if self.showLogs:
			print("simulator log")
			print("--------------------------------------------------------------------------------")
			print(simulatorLog)
			print("--------------------------------------------------------------------------------")		
	
		print()
		if (not self.__guiMode):
			try:
				result = self.checkSimulatorOutput(simulatorLog)
				
				if (result == True):
					print("Testbench '%s': PASSED" % testbenchName)
				else:
					print("Testbench '%s': FAILED" % testbenchName)
					
			except SimulatorException as ex:
				raise TestbenchException("PoC.ns.module", testbenchName, "'SIMULATION RESULT = [PASSED|FAILED]' not found in simulator output.") from ex
		
