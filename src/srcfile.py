# -*- coding: utf-8 -*-
#
# Copyright (c) 2013 CERN
# Author: Pawel Szostek (pawel.szostek@cern.ch)
#
# This file is part of Hdlmake.
#
# Hdlmake is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Hdlmake is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Hdlmake.  If not, see <http://www.gnu.org/licenses/>.
#

from dep_solver import IDependable
import os
import msg as p
import global_mod
import flow
import path as path_mod


class File(object):
    def __init__(self, path):
        self.path = path

    @property
    def name(self):
        return os.path.basename(self.path)

    @property
    def purename(self):
        return os.path.splitext(self.name)[0]

    @property
    def dirname(self):
        return os.path.dirname(self.path)
    
    def rel_path(self, dir=None):
        import path
        if dir is None:
            dir = os.getcwd()
        return path.relpath(self.path, dir)

    def __str__(self):
        return self.path

    def __eq__(self, other):
        _NOTFOUND = object()
        v1, v2 = [getattr(obj, "path", _NOTFOUND) for obj in [self, other]] 
        if v1 is _NOTFOUND or v2 is _NOTFOUND:
            return False
        elif v1 != v2:
            return False
        return True

    def __hash__(self):
        return hash(self.path)

    def __cmp__(self, other):
        if self.path < other.path:
            return -1
        if self.path == other.path:
            return 0
        if self.path > other.path:
            return 1

    def __ne__(self, other):
        return not self.__eq__(other)

    def isdir(self):
        return os.path.isdir(self.path)

    def show(self):
        p.rawprint(self.path)

    def extension(self):
        tmp = self.path.rsplit('.')
        ext = tmp[len(tmp)-1]
        return ext

   
class SourceFile(IDependable, File):
    cur_index = 0

    def __init__(self, path, library=None):
        IDependable.__init__(self)
        File.__init__(self, path)
        if not library:
            library = "work"

        self.library = library

    def gen_index(self):
        self.__class__.cur_index = self.__class__.cur_index+1
        return self.__class__.cur_index


class VHDLFile(SourceFile):
    def __init__(self, path, library=None, vcom_opt=None):
        SourceFile.__init__(self, path, library)
        self.__create_deps()
        if not vcom_opt:
            self.vcom_opt = ""
        else:
            self.vcom_opt = vcom_opt

    def __check_encryption(self):
        f = open(self.path, "rb")
        s = f.read(3)
        f.close()
        if(s == b'Xlx'):
            return True
        else:
            return False

    def __create_deps(self):
        if self.__check_encryption():
            self.dep_index = SourceFile.gen_index(self)
            self._dep_fixed = True
        else:
            self.dep_requires = list(self.__search_use_clauses())
            self.dep_provides = list(self.__search_packages())
        p.vprint(self.path + " provides " + str(self.dep_provides))
        p.vprint(self.path + " requires " + str(self.dep_requires))

    def __search_use_clauses(self):
        """
        Reads a file and looks for 'use' clause. For every 'use' with
        non-standard library a tuple (lib, file) is returned in a list.

        """
        # Modification here! global_mod.top_module.action does not
        # get set for top module in time. FIX this

        std_libs = ['std', 'ieee']
        if global_mod.top_module.action == "simulation":
            try:
                if global_mod.top_module.sim_tool == "isim":
                    std_libs = flow.XilinxsiminiReader().get_libraries()
                elif global_mod.top_module.sim_tool == "vsim":
                    std_libs = flow.ModelsiminiReader().get_libraries()
                else:
                    p.warning("Could not determine simulation tool. Defaulting to Modelsim")
                    std_libs = flow.MODELSIM_STANDARD_LIBS
            except RuntimeError as e:
             #std_libs =  flow.MODELSIM_STANDARD_LIBS
                print "I/O error: ({0})".format(e.message)
                p.error("Picking standard Modelsim simulation libraries. Try to fix the error.")
                std_libs = flow.MODELSIM_STARDAND_LIBS
        elif global_mod.top_module.action == "synthesis":
            print("setting std libs for synthesis...")
            if global_mod.top_module.target == "xilinx":
                std_libs = flow.ISE_STANDARD_LIBS
            elif global_mod.top_module.target == "altera":
                std_libs = flow.QUARTUS_STANDARD_LIBS

        import re
        try:
            f = open(self.path, "r")
            text = f.readlines()
        except UnicodeDecodeError:
            return []

        use_pattern = re.compile("^[ \t]*use[ \t]+([^; ]+)[ \t]*;.*$")
        lib_pattern = re.compile("([^.]+)\.([^.]+)\.all")

        use_lines = []
        for line in text:
            #identifiers and keywords are case-insensitive in VHDL
            line_lower = line.lower()
            m = re.match(use_pattern, line_lower)
            if m is not None:
                use_lines.append(m.group(1))

        ret = set() 
        for line in use_lines:
            m = re.match(lib_pattern, line)
            if m is not None:
                #omit standard libraries
                if (m.group(1)).lower() in std_libs:
                    continue
                if self.library != "work":
                    #if a file is put in a library, `work' points this library
                    new = (self.library.lower(), m.group(2).lower())
                else:
                    new = (m.group(1).lower(), m.group(2).lower())
                #dont add if the tuple is already in the list
                if new in self.dep_provides:
                    continue
                ret.add(new)

        f.close()
        return ret

    def __search_packages(self):
        """
        Reads a file and looks for package clase. Returns list of packages' names
        from the file
        """
        import re
        f = open(self.path, "r")
        try:
            text = f.readlines()
        except UnicodeDecodeError:
            return []

        package_pattern = re.compile("^[ \t]*package[ \t]+([^ \t]+)[ \t]+is[ \t]*.*$")

        ret = set() 
        for line in text:
            #identifiers and keywords are case-insensitive in VHDL
            line = line.lower()
            m = re.match(package_pattern, line)
            if m is not None:
                ret.add((self.library.lower(), m.group(1).lower()))

        f.close()
        return ret


class VerilogFile(SourceFile):
    def __init__(self, path, library=None, vlog_opt=None, include_dirs=None):
        if not library:
            library = "work"
        SourceFile.__init__(self, path, library)
        if not vlog_opt:
            self.vlog_opt = ""
        else:
            self.vlog_opt = vlog_opt
        self.include_dirs = []
        if include_dirs:
            self.include_dirs.extend(include_dirs)
        self.include_dirs.append(path_mod.relpath(self.dirname))
        self.__create_deps()

    def __create_deps(self):
#        self.dep_requires = self.__search_includes()
#        self.dep_provides = self.name
        if global_mod.env.iverilog_path:
            self.dep_requires = []
            deps = self.__get_iverilog_dependencies()
            self.dep_requires.extend(deps)
        else:
            self.dep_requires = self.__search_includes()
        self.dep_provides = self.name

    def __get_iverilog_dependencies(self):
           #TODO: Check to see dependencies.list doesn't exist already
        if self.path.endswith(".vh") and global_mod.top_module.sim_tool == "iverilog":
            return []
        inc_dirs = []
        #inc_dirs = global_mod.top_module.include_dirs
        inc_dirs = self.include_dirs
        if global_mod.mod_pool:
            inc_dirs.extend([os.path.relpath(m.path) for m in global_mod.mod_pool])
        inc_dirs = list(set(inc_dirs))
        vlog_opt = global_mod.top_module.vlog_opt
        depFileName = "dependencies.list"
        command = "iverilog -DSIMULATE -Wno-timescale -t null -M" + depFileName
        command += "".join(map(lambda x: " -y"+x, inc_dirs))
        command += "".join(map(lambda x: " -I"+x, inc_dirs))
        # TODO: Have to find a way to handle this cleanly
        if self.rel_path().find("config_romx_llrf4") > -1:
            command += " " + vlog_opt
        else:
            command += " " + vlog_opt + " " + self.rel_path()
        retOsSystem = os.system(command)
        if retOsSystem and retOsSystem != 256:
            print "Dependencies not Met"
            print command, self.include_dirs, inc_dirs, global_mod.mod_pool
            quit()
        elif retOsSystem == 256:
            print command
            pass
        depFile = open(depFileName,"r")
        depFiles = list(set([l.strip() for l in depFile.readlines()]))
        depFile.close()
        return depFiles

    def __search_includes(self):
        import re
        f = open(self.path, "r")
        try:
            text = f.readlines()
        except UnicodeDecodeError:
            return []
        include_pattern = re.compile("^[ \t]*`include[ \t]+\"([^ \"]+)\".*$")
        ret = []
        for line in text:
            #in Verilog and SV identifiers are case-sensitive
            m = re.match(include_pattern, line)
            if m is not None:
                ret.append(m.group(1))
        f.close()
        return ret


class SVFile(VerilogFile):
    pass


class UCFFile(File):
    pass


class TCLFile(File):
    pass


class XISEFile(File):
    pass


class CDCFile(File):
    pass


class SignalTapFile(File):
    pass


class SDCFile(File):
    pass


class QIPFile(File):
    pass


class DPFFile(File):
    pass


class NGCFile(SourceFile):
    def __init__(self, path):
        SourceFile.__init__(self, path)
        self._dep_fixed = True


class WBGenFile(File):
    pass


class SourceFileSet(list):
    def __init__(self):
        super(SourceFileSet, self).__init__()
        self = []

    def __str__(self):
        return str([str(f) for f in self])

    def add(self, files):
        if isinstance(files, str):
            raise RuntimeError("Expected object, not a string")
        elif files is None:
            p.vprint("Got None as a file.\n Ommiting")
        else:
            try:
                for f in files:
                    if f not in self:
                        self.append(f)
            except:  # single file, not a list
                if files not in self:
                    self.append(files)

    def filter(self, type):
        out = SourceFileSet()
        for f in self:
            if isinstance(f, type):
                out.add(f)
        return out

    def inversed_filter(self, type):
        out = SourceFileSet()
        for f in self:
            if not isinstance(f, type):
                out.add(f)
        return out

    def get_libs(self):
        ret = set()
        for file in self:
            try:
                ret.add(file.library)
            except:
                pass
        return ret


class SourceFileFactory:
    def new(self, path, library=None, vcom_opt=None, vlog_opt=None, include_dirs=None):
        if path is None or path == "":
            raise RuntimeError("Expected a file path, got: "+str(path))
        if not os.path.isabs(path):
            path = os.path.abspath(path)
        tmp = path.rsplit('.')
        extension = tmp[len(tmp)-1]
        p.vprint("SFF> " + path)

        nf = None
        if extension == 'vhd' or extension == 'vhdl' or extension == 'vho':
            nf = VHDLFile(path, library, vcom_opt)
        elif extension == 'v' or extension == 'vh' or extension == 'vo' or extension == 'vm':
            nf = VerilogFile(path, library, vlog_opt, include_dirs)
        elif extension == 'sv' or extension == 'svh':
            nf = SVFile(path, library, vlog_opt, include_dirs)
        elif extension == 'ngc':
            nf = NGCFile(path)
        elif extension == 'ucf':
            nf = UCFFile(path)
        elif extension == 'cdc':
            nf = CDCFile(path)
        elif extension == 'wb':
            nf = WBGenFile(path)
        elif extension == 'tcl':
            nf = TCLFile(path)
        elif extension == 'xise' or extension == 'ise':
            nf = XISEFile(path)
        elif extension == 'stp':
            nf = SignalTapFile(path)
        elif extension == 'sdc':
            nf = SDCFile(path)
        elif extension == 'qip':
            nf = QIPFile(path)
        elif extension == 'dpf':
            nf = DPFFile(path)
        return nf
