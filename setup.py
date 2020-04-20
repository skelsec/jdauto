from setuptools import setup, find_packages
import re

VERSIONFILE="jdauto/_version.py"
verstrline = open(VERSIONFILE, "rt").read()
VSRE = r"^__version__ = ['\"]([^'\"]*)['\"]"
mo = re.search(VSRE, verstrline, re.M)
if mo:
    verstr = mo.group(1)
else:
    raise RuntimeError("Unable to find version string in %s." % (VERSIONFILE,))


setup(
	# Application name:
	name="jdauto",

	# Version number (initial):
	version=verstr,

	# Application author details:
	author="Tamas Jos",
	author_email="info@skelsec.com",

	# Packages
	packages=find_packages(),

	# Include additional files into the package
	include_package_data=True,


	# Details
	url="https://github.com/skelsec/jdauto",

	zip_safe = True,
	#
	# license="LICENSE.txt",
	description="Autocollect service for Jackdaw",
	long_description="Autocollect service for Jackdaw",

	# long_description=open("README.txt").read(),
	python_requires='>=3.6',
	classifiers=(
		"Programming Language :: Python :: 3.6",
		"License :: OSI Approved :: MIT License",
		"Operating System :: OS Independent",
	),
	install_requires=[
		'jackdaw>=0.2.6',
        'aiosmb>=0.2.11',
        'msldap',
		'pypykatz>=0.3.9',
	],
	#entry_points={
	#	'console_scripts': [
	#		'jdauto = XXXX',
	#	],
	#}
)