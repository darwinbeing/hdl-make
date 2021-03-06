#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2013, 2014 CERN
# Author: Pawel Szostek (pawel.szostek@cern.ch)
# Multi-tool support by Javier D. Garcia-Lasheras (javier@garcialasheras.com)
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

from __future__ import print_function
from dep_file import DepFile
import new_dep_solver as dep_solver
import logging
import sys
import global_mod
from action import Action

import importlib



class GenerateSynthesisMakefile(Action):

    def _check_manifest(self):
        # NOTE: top_module is not used in synthesis!!
        if not self.modules_pool.get_top_module().syn_top:
            logging.error("syn_top variable must be set in the top manifest.")
            sys.exit("Exiting")
        if not self.modules_pool.get_top_module().syn_tool:
            logging.error("syn_tool variable must be set in the top manifest.")
            sys.exit("Exiting")


    def run(self):
        self._check_all_fetched_or_quit()
        self._check_manifest()
        tool_object = global_mod.tool_module.ToolControls()
        self._generate_synthesis_makefile(tool_object)


    def _generate_synthesis_makefile(self, tool_object):
            
        tool_info = tool_object.get_keys()
        if sys.platform == 'cygwin':
            bin_name = tool_info['windows_bin']
        else:
            bin_name = tool_info['linux_bin']
        path_key = tool_info['id'] + '_path'
        version_key = tool_info['id'] + '_version'
        name = tool_info['name']

        if global_mod.env[path_key]:
            tool_path = global_mod.env[path_key]
        else:
            tool_path = ""
        
        logging.info("Generating synthesis makefile for " + name)
        tool_object.generate_synthesis_makefile(top_mod=self.modules_pool.get_top_module(),
                                                         tool_path=tool_path)
        logging.info("Synthesis makefile generated.")

