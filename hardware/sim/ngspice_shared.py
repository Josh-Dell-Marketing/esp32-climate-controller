"""Minimal ctypes driver for the ngspice shared library that ships with KiCad.

Usage:
    ng = NgSpice()                     # loads KiCad's ngspice.dll
    vecs = ng.run_file("test.cir")     # sources the netlist, runs it, returns {name: numpy array}

Each run reads a netlist file, inlines its .include files, runs the analysis given in the netlist
(.tran / .op / .dc), copies every vector of the current plot into numpy
arrays and then removes the circuit, so many circuits can run in one process.
"""
import ctypes
import os
import re
from ctypes import (CFUNCTYPE, POINTER, Structure, c_bool, c_char_p, c_double,
                    c_int, c_short, c_void_p)

import numpy as np

DEFAULT_DLL = r"C:\Program Files\KiCad\10.0\bin\ngspice.dll"


class _VectorInfo(Structure):
    _fields_ = [
        ("v_name", c_char_p),
        ("v_type", c_int),
        ("v_flags", c_short),
        ("v_realdata", POINTER(c_double)),
        ("v_compdata", c_void_p),
        ("v_length", c_int),
    ]


_SendChar = CFUNCTYPE(c_int, c_char_p, c_int, c_void_p)
_SendStat = CFUNCTYPE(c_int, c_char_p, c_int, c_void_p)
_ControlledExit = CFUNCTYPE(c_int, c_int, c_bool, c_bool, c_int, c_void_p)
_SendData = CFUNCTYPE(c_int, c_void_p, c_int, c_int, c_void_p)
_SendInitData = CFUNCTYPE(c_int, c_void_p, c_int, c_void_p)
_BGThreadRunning = CFUNCTYPE(c_int, c_bool, c_int, c_void_p)


class NgSpice:
    def __init__(self, dll_path=DEFAULT_DLL, verbose=False):
        dll_dir = os.path.dirname(dll_path)
        if hasattr(os, "add_dll_directory"):
            os.add_dll_directory(dll_dir)
        self.verbose = verbose
        self.log = []
        self.lib = ctypes.CDLL(dll_path)

        # keep references to the callbacks so they are not garbage collected
        self._cb_char = _SendChar(self._on_char)
        self._cb_stat = _SendStat(lambda *a: 0)
        self._cb_exit = _ControlledExit(self._on_exit)
        self._cb_data = _SendData(lambda *a: 0)
        self._cb_init = _SendInitData(lambda *a: 0)
        self._cb_bg = _BGThreadRunning(lambda *a: 0)

        self.lib.ngSpice_Init.argtypes = [_SendChar, _SendStat, _ControlledExit,
                                          _SendData, _SendInitData, _BGThreadRunning, c_void_p]
        self.lib.ngSpice_Command.argtypes = [c_char_p]
        self.lib.ngSpice_Circ.argtypes = [POINTER(c_char_p)]
        self.lib.ngGet_Vec_Info.argtypes = [c_char_p]
        self.lib.ngGet_Vec_Info.restype = POINTER(_VectorInfo)
        self.lib.ngSpice_CurPlot.restype = c_char_p
        self.lib.ngSpice_AllVecs.argtypes = [c_char_p]
        self.lib.ngSpice_AllVecs.restype = POINTER(c_char_p)
        self.lib.ngSpice_Init(self._cb_char, self._cb_stat, self._cb_exit,
                              self._cb_data, self._cb_init, self._cb_bg, None)

    def _on_char(self, text, _id, _user):
        s = text.decode(errors="replace")
        self.log.append(s)
        if self.verbose:
            print(s)
        return 0

    def _on_exit(self, status, unload, quit_, _id, _user):
        self.log.append(f"ngspice exit request status={status}")
        return 0

    def cmd(self, command):
        return self.lib.ngSpice_Command(command.encode())

    @staticmethod
    def expand(path, _depth=0):
        """Read a netlist and inline every .include / .lib file (paths relative to the file)."""
        base = os.path.dirname(os.path.abspath(path))
        lines = []
        with open(path, encoding="utf-8") as f:
            for line in f.read().splitlines():
                m = re.match(r'^\s*\.(include|inc)\s+"?([^"]+?)"?\s*$', line, re.I)
                if m and _depth < 5:
                    inc = os.path.join(base, m.group(2))
                    lines.append(f"* ---- begin {m.group(2)} ----")
                    lines += [l for l in NgSpice.expand(inc, _depth + 1) if l.strip().lower() != ".end"]
                    lines.append(f"* ---- end {m.group(2)} ----")
                else:
                    lines.append(line)
        return lines

    def run_file(self, path):
        """Load a netlist (includes inlined), run it and return all vectors of the result plot."""
        self.log = []
        self.cmd("destroy all")
        lines = self.expand(path)
        arr = (c_char_p * (len(lines) + 1))(*[l.encode() for l in lines], None)
        self.lib.ngSpice_Circ(arr)
        rc = self.cmd("run")
        errors = [l for l in self.log if "error" in l.lower() and "warning" not in l.lower()]
        plot = self.lib.ngSpice_CurPlot().decode()
        names_p = self.lib.ngSpice_AllVecs(plot.encode())
        out = {}
        i = 0
        while names_p and names_p[i]:
            name = names_p[i].decode()
            info = self.lib.ngGet_Vec_Info(f"{plot}.{name}".encode())
            if info and info.contents.v_realdata:
                n = info.contents.v_length
                out[name.lower()] = np.ctypeslib.as_array(info.contents.v_realdata, shape=(n,)).copy()
            i += 1
        self.cmd("remcirc")
        if rc != 0 or not out or plot.startswith("const"):
            raise RuntimeError(f"ngspice run of {path} failed (rc={rc}, plot={plot}).\n"
                               + "\n".join(self.log[-40:]))
        if errors and self.verbose:
            print("\n".join(errors))
        return out
