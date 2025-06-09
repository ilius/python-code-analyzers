#!/usr/bin/env python3

import json
import os
import subprocess
import time
from collections.abc import Iterable
from os.path import isfile, join, normpath
from typing import IO, NamedTuple


def listFilesRecursiveRelPath(direc: str) -> Iterable[str]:
	"""
	Iterate over relative paths of all files (directly/indirectly)
	inside given directory.
	"""
	direc = normpath(direc)  # remove trailing slash/sep or leading "./"
	direcLen = len(direc) + 1
	for root, _subDirs, files in os.walk(direc):
		rootRel = root[direcLen:]
		for fname in files:
			yield join(rootRel, fname)


def readIO(iox: IO[bytes]) -> list[str]:
	return [line for line in iox.read().decode("utf-8").split("\n") if line.strip()]


class Result(NamedTuple):
	time: int  # ms
	error: int
	output: int
	output_other: int
	path: str


results: dict[str, Result] = {}

if isfile("mypy-analyzer.json"):
	with open("mypy-analyzer.json", encoding="utf-8") as file:
		raw_results = json.load(file)
	results = {key: Result(*row) for key, row in raw_results.items()}


def save() -> None:
	with open("mypy-analyzer.json", "w", encoding="utf-8") as file:
		json.dump(results, file, indent="\t")


save()
try:
	for fpath in listFilesRecursiveRelPath("."):
		if not fpath.endswith(".py"):
			continue
		if fpath in results:
			continue
		t0 = time.time()
		os.environ["NO_COLOR"] = "1"
		os.environ.pop("FORCE_COLOR", None)
		print(f"Running: {fpath!r}")
		p = subprocess.Popen(
			["mypy", fpath],
			stderr=subprocess.PIPE,
			stdout=subprocess.PIPE,
		)
		try:
			p.wait(timeout=5)
		except subprocess.TimeoutExpired:
			print("Timeout:", fpath)
		dt = time.time() - t0
		assert p.stdout
		assert p.stderr
		out = readIO(p.stdout)
		err = readIO(p.stderr)
		if out == ["Success: no issues found in 1 source file"]:
			out = []
		output_other = 0
		for line in out:
			if ".py:" not in line:
				continue
			tmpPath, _, _ = line.partition(":")
			if tmpPath != fpath:
				output_other += 1
		res = Result(
			time=int(dt * 1000),
			error=len(err),
			output=len(out) - output_other,
			output_other=output_other,
			path=fpath,
		)
		results[fpath] = res
		save()
except KeyboardInterrupt:
	print("Cancelled by Ctrl+C")

save()


resultList = [res for res in results.values() if res.output > 0 or res.error > 0]


def sortKey(res: Result):
	return (res.output_other, res.time//100, res.output)


for res in sorted(resultList, key=sortKey):
	print(res)
