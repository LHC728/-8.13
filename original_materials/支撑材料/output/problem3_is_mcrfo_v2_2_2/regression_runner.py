#!/usr/bin/env python3
"""Standalone regression runner: v1 vs v2.1 vs v2.2.2"""
import subprocess,sys,os
os.chdir("/home/user/workspace")
reg_seeds=list(range(1000,1010))
# See problem3_is_mcrfo_final_v2_2_2.py main() for the full regression logic
print("Run: python code/problem3_is_mcrfo_final_v2_2_2.py")
