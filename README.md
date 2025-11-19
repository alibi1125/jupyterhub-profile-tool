# jupyterhub-profile-tool

A Jupyterhub service that allows users to create, modify and delete Jupyterhub spawner profiles

## What it is, how it works

The Python programs in this package are built to allow users to create and manage their own profile options for Wrapspawner. [This Wrapspanwer fork on GitHub](https://github.com/alibi1125/wrapspawner) provides the matching counterparts with the ImportedProfilesSpawner and ServiceProfilesSpawner classes.

This application implements

- A website for users to manage their profiles on. It uses JupyterHub's own design elements as much as possible to provide an uninterrupted experience.
- A file-based loading and storing solution for user profiles. Every user's profiles are stored as JSON files in their home directories. The aim was to keep these definitions short, readable and easily interpretable for users of the standard wrapspawner.ProfilesSpawner.
- Schema checking in both backend and frontend to make profile management reliable and resilient.

`profilemaker.py` contains a Tornado-based web application that provides the website for users to manage their profiles on and an API to access the main features of the profile management solution (both for internal and external use). It is designed to be run as a JupyterHub-managed service and relies on JupyterHub's user authentication mechanisms.

`userprofileworker.py` contains a relatively simple Python program that reads, writes, updates and deletes profile definitions from JSON files. It serves as a transaction backend for `profilemaker.py`, to be run with the privileges of the authenticated web user. Users and admins never have to run it directly.
