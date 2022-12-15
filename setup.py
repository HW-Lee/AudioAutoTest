import setuptools
import os

# Note: release commands
#    $ python3 setup.py bdist_wheel
#    $ python3 -m twine upload dist/python_audio_autotest-1.2.4-py3-none-any.whl

with open("README.md", "r") as fh:
    long_description = fh.read()

os.system("mkdir -p ./pyaatlibs/apk/")
os.system("cp ./apk/debug/*.apk ./pyaatlibs/apk/")

packages = setuptools.find_packages()
packages = [package for package in packages if package.startswith("pyaat")]

install_reqs = [
    "androidviewclient==22.3.1",
    "numpy==1.22.0",
    "scipy==1.7.3",
    "scikit-learn==1.0.2",
    "matplotlib==3.5.3",
    "librosa==0.9.2",
    "sounddevice==0.4.5"
]

setuptools.setup(
    name="python-audio-autotest",
    version="1.5.1",
    scripts=[] ,
    author="Hao-Wei Lee",
    author_email="hwinnerlee@gmail.com, hwlee@google.com",
    description="This is a auto-testing framework of audio functions for Android devices.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/HW-Lee/AudioAutoTest",
    install_requires=install_reqs,
    packages=packages,
    include_package_data=True,
    package_data={
        "pyaatlibs": ["apk/*.apk", "tests/*.py"]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
)

os.system("rm -rf ./pyaatlibs/apk/")
