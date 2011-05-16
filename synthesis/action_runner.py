#!/usr/bin/python
# -*- coding: utf-8 -*-

import re
import fileinput
import sys
import path
import path
import time
import os
from connection import Connection
import random
import string
import global_mod
import msg as p
import optparse
from module import Module
from helper_classes import Manifest, ManifestParser
from fetch import ModulePool

class ActionRunner(object):
    def __init__(self, modules_pool, connection):
        self.modules_pool = modules_pool
        self.connection = connection

    def generate_pseudo_ipcore(self):
        from depend import MakefileWriter
        tm = modules_pool.get_top_module()
        make_writer = MakefileWriter()

        file_deps_dict = tm.generate_deps_for_vhdl_in_modules()
        make_writer.generate_pseudo_ipcore_makefile(file_deps_dict)

        if global_mod.options.nodel != True:
            os.remove("Makefile.ipcore")
        os.system("make -f Makefile.ipcore")

    def fetch(self):
        self.modules_pool.fetch_all()
        p.vprint(str(self.modules_pool))

    def generate_modelsim_makefile(self):
        from dep_solver import DependencySolver
        from depend import MakefileWriter
        solver = DependencySolver()
        make_writer = MakefileWriter()

        pool = self.modules_pool
        if not pool.is_everything_fetched():
            p.echo("A module remains unfetched. Fetching must be done prior to makefile generation")
            quit()
        tm = pool.get_top_module()
        flist = tm.build_global_file_list();
        flist_sorted = solver.solve(flist);

        make_writer.generate_modelsim_makefile(flist_sorted, tm)

    def generate_ise_makefile(self, top_mod):
        from depend import MakefileWriter
        make_writer = MakefileWriter()
        make_writer.generate_ise_makefile()

    def generate_ise_project(self, top_mod):
        from flow import ISEProject, ISEProjectProperty
        if not self.modules_pool.is_everything_fetched():
            p.echo("A module remains unfetched. Fetching must be done prior to makefile generation")
            quit()
        if os.path.exists(top_mod.syn_project):
            self.__update_existing_ise_project()
        else:
            self.__create_new_ise_project()

    def __update_existing_ise_project(self):
        from dep_solver import DependencySolver
        from flow import ISEProject, ISEProjectProperty

        top_mod = self.modules_pool.get_top_module()
        fileset = top_mod.build_global_file_list()
        solver = DependencySolver()
        fileset = solver.solve(fileset)

        prj = ISEProject()
        prj.add_files(fileset)
        prj.add_libs(fileset.get_libs())
        prj.load_xml(top_mod.syn_project)
        prj.emit_xml(top_mod.syn_project)

    def __create_new_ise_project(self):
        from dep_solver import DependencySolver
        from flow import ISEProject, ISEProjectProperty

        top_mod = self.modules_pool.get_top_module()
        fileset = top_mod.build_global_file_list()
        solver = DependencySolver()
        fileset = solver.solve(fileset)

        prj = ISEProject()
        prj.add_files(fileset)
        prj.add_libs(fileset.get_libs())

        prj.add_property(ISEProjectProperty("Device", top_mod.syn_device))
        prj.add_property(ISEProjectProperty("Device Family", "Spartan6"))
        prj.add_property(ISEProjectProperty("Speed Grade", top_mod.syn_grade))
        prj.add_property(ISEProjectProperty("Package", top_mod.syn_package))
        #    prj.add_property(ISEProjectProperty("Implementation Top", "Architecture|"+top_mod.syn_top))
        prj.add_property(ISEProjectProperty("Implementation Top", "Architecture|"+top_mod.syn_top))
        prj.add_property(ISEProjectProperty("Manual Implementation Compile Order", "true"))
        prj.add_property(ISEProjectProperty("Auto Implementation Top", "false"))
        prj.add_property(ISEProjectProperty("Implementation Top Instance Path", "/"+top_mod.syn_top))
        prj.emit_xml(top_mod.syn_project)

    def run_local_synthesis(self):
        tm = self.modules_pool.get_top_module()
        if tm.target == "xilinx":
            if not os.path.exists("run.tcl"):
                self.__generate_tcl()
            os.system("xtclsh run.tcl");
        else:
            p.echo("Target " + tm.target + " is not synthesizable")

    def run_remote_synthesis(self):
        from srcfile import SourceFileFactory, TCLFile
        ssh = self.connection
        tm = self.modules_pool.get_top_module()
        cwd = os.getcwd()

        p.vprint("The program will be using ssh connection: "+str(ssh))
        if not ssh.is_good():
            p.echo("SSH connection failure. Remote host doesn't response.")
            quit()

        if not os.path.exists(tm.fetchto):
            p.echo("There are no modules fetched. Are you sure it's correct?")

        files = self.modules_pool.build_global_file_list()
        tcl = self.__search_tcl_file()
        if tcl == None:
            self.__generate_tcl()
            tcl = "run.tcl"

        sff = SourceFileFactory()
        files.add(sff.new(tcl))
        files.add(sff.new(tm.syn_project))

        dest_folder = ssh.transfer_files_forth(files, tm.name)
        syn_cmd = "cd "+dest_folder+cwd+" && xtclsh run.tcl"
        if not os.path.exists("run.tcl"):
            self.__generate_tcl()

        p.vprint("Launching synthesis on " + str(ssh) + ": " + syn_cmd)
        ret = ssh.system(syn_cmd)
        if ret == 1:
            p.echo("Synthesis failed. Nothing will be transfered back")
            quit()

        cur_dir = os.path.basename(cwd)
        os.chdir("..")
        ssh.transfer_files_back(what=dest_folder+cwd, where=".")
        os.chdir(cur_dir)
        if global_mod.options.nodel != True:
            p.echo("Deleting synthesis folder")
            ssh.system('rm -rf ' + dest_folder)

    def __search_tcl_file(self, directory = None):
        import re
        pat = re.compile("^.*?\.tcl$")
        if directory == None:
            directory = "."
        dir = os.listdir(directory)
        tcls = []
        for file in dir:
            match = re.match(pat, file)
            if match != None:
                tcls.append(file)
        if len(tcls) == 0:
            return None
        if len(tcls) > 1:
            p.rawprint("Multiple tcls in the current directory!")
            p.rawprint(str(tcls))
            quit()
        return tcls[0]

    def __generate_tcl(self):
        tm = self.modules_pool.get_top_module()
        f = open("run.tcl","w");
        f.write("project open " + tm.syn_project + '\n')
        f.write("process run {Generate Programming Files} -force rerun_all\n")
        f.close()


    def generate_fetch_makefile(self):
        from depend import MakefileWriter
        pool = self.modules_pool
        if not pool.is_everything_fetched():
            p.echo("A module remains unfetched. Fetching must be done prior to makefile generation")
            quit()
        make_writer = MakefileWriter()
        make_writer.generate_fetch_makefile(pool)
