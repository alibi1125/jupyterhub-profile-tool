from setuptools import setup

with open("README.md") as f:
    long_description = f.read()

setup(
    name="jupyterhub_profile_tool",
    packages=["jupyterhub_profile_tool"],
    include_package_data=True,
    version="0.0.4.dev1",
    description="""A Jupyterhub service that allows users to create, modify and delete Jupyterhub spawner profiles""",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Alexander Birk",
    author_email="alexander.birk@ki.uni-stuttgart.de",
    url="https://github.tik.uni-stuttgart.de/KI/jupyterhub-profile-tool",
    license="BSD",
    platforms="Linux",
    keywords=["Jupyter", "Jupyterhub", "Service"],
    classifiers=[
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Science/Research",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
    ],
    project_urls={
        "Bug Reports": "https://github.tik.uni-stuttgart.de/KI/jupyterhub-profile-tool/issues",
        "Source": "https://github.tik.uni-stuttgart.de/KI/jupyterhub-profile-tool",
        "About Jupyterhub": "http://jupyterhub.readthedocs.io/en/latest/",
        "Jupyter Project": "http://jupyter.org",
    },
    python_requires=">=3.9",
    install_requires=[
        "jupyterhub>=1.5.1",
        "tornado",
        "schema",
    ],
)
