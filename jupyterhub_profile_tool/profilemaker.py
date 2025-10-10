import argparse
import json
import subprocess
import os
import sys
import binascii
import logging

from tornado import escape, ioloop, web
from tornado.log import app_log
from urllib.parse import urljoin

from traitlets import Unicode

from jupyterhub.services.auth import HubOAuthenticated, HubOAuthCallbackHandler

class ProfileMakerHandler(HubOAuthenticated, web.RequestHandler):
    """Manage Profiles for JupyterHub wrapspawner"""

    def initialize(self, prefix):
        self.prefix = prefix

    @web.authenticated
    def prepare(self):
        self.user = self.get_current_user()
        self.manager_instance = ProfileManager(self.user["name"])

    def get(self):
        profiles = self.manager_instance.get_all_profiles()
        self.render("page.html", base_url="/hub/", user=self.user["name"], profiles=profiles, prefix=self.prefix)
    
    def post(self):
        spawner_options = {"req_nprocs": "1", "req_memory": "100mb", "req_partition": "fastlane", "req_runtime": "00:10:00"}
        profile = {"description": "Test profile", "options": spawner_options}
        stringified_profile = json.dumps(profile)
        self.manager_instance.create_profile(stringified_profile)

class ProfileGetHandler(HubOAuthenticated, web.RequestHandler):
    """Gets the user's profiles"""

    @web.authenticated
    def prepare(self):
        self.user = self.get_current_user()
        self.manager_instance = ProfileManager(self.user["name"])

    def get(self, profile_id):
        profiles = self.manager_instance.get_singular_profile(profile_id)
        if profiles is None:
            self.set_status(404)
            self.finish({"error": "Profile not found"})
            return
        self.write(profiles)

class ProfileCreateHandler(HubOAuthenticated, web.RequestHandler):
    """Creates an entirely new profile for the current user"""

    @web.authenticated
    def prepare(self):
        self.user = self.get_current_user()
        self.manager_instance = ProfileManager(self.user["name"])

    def post(self):
        data = self.request.body.decode('utf-8')
        self.manager_instance.create_profile(data)

class ProfileUpdateHandler(HubOAuthenticated, web.RequestHandler):
    """Creates an entirely new profile for the current user"""

    @web.authenticated
    def prepare(self):
        self.user = self.get_current_user()
        self.manager_instance = ProfileManager(self.user["name"])

    def post(self, profile_id):
        data = self.request.body.decode('utf-8')
        self.manager_instance.update_profile(profile_id, data)

class ProfileDeleteHandler(HubOAuthenticated, web.RequestHandler):
    """Creates an entirely new profile for the current user"""

    @web.authenticated
    def prepare(self):
        self.user = self.get_current_user()
        self.manager_instance = ProfileManager(self.user["name"])

    def post(self, profile_id):
        self.manager_instance.delete_profile(profile_id)

class ProfileManager():
    """Performs the profile management in the background, keeping the Handlers simple"""

    class FileOpException(Exception):
        pass

    home_base_dir = Unicode(
        "/home/",
        config=True
    )

    def __init__(self, username):
        app_log.debug(f"Instantiating profile manager for user {username}")
        self.username = username
        self.user_profile_path = os.path.join(self.home_base_dir, username, ".jupyterhub", "user_profiles.json")
    
    def __profile_id_to_index(self, profile_id):
        return int(profile_id.strip("prof_"))
    
    def __index_to_profile_id(self, index):
        return f"prof_{index}"
    
    def create_profile(self, profile):
        self._file_op("write", profile)
    
    def update_profile(self, profile_id, new_profile):
        old_profile_index = self.__profile_id_to_index(profile_id)
        self._file_op("update", entry_index=old_profile_index, new_profile=new_profile)
    
    def delete_profile(self, profile_id):
        old_profile_index = self.__profile_id_to_index(profile_id)
        self._file_op("delete", entry_index=old_profile_index)

    def get_singular_profile(self, profile_id):
        profiles = self.get_all_profiles()
        return next((p for p in profiles if p["profile_id"] == profile_id), None)

    def get_all_profiles(self):
        profiles = self._file_op("read")
        try:
            loaded_profiles = json.loads(profiles)
        except json.JSONDecodeError:
            app_log.error("Could not parse the JSON entries in the profiles file.")
            loaded_profiles = []
        for index, profile in loaded_profiles:
            profile["profile_id"] = self.__index_to_profile_id(index)
        return loaded_profiles

    def _file_op(self, action, entry_index=None, new_profile=None):
        """Handles interactions with JSON profile files"""
        if action not in {'read', 'write', 'delete', 'update'}:
            raise ValueError("`action` needs to be one of `read`, `write`, `delete`, `update`.")
        cmd = [
            sys.executable,
            '-m', 'jupyterhub_profile_tool.userprofileworker',
            '--path', self.user_profile_path,
            '--action', action,
            ]
        if entry_index:
            cmd.extend(['--entry_index', str(entry_index)])
        if new_profile:
            cmd.append(new_profile)
        subproc_result = subprocess.run(cmd, text=True, user=self.username)
        if subproc_result.returncode > 0:
            app_log.error(f"Errors encountered in subprocess: {subproc_result.stderr}")
            raise self.FileOpException()
        elif subproc_result.stderr != '':
            app_log.warning(f"Problems encountered in subprocess: {subproc_result.stderr}")
        if action == 'read':
            return subproc_result.stdout


def main():
    args = parse_arguments()
    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)
    app_log.addHandler(logging.handlers.SysLogHandler("/dev/log"))
    if args["debug"]:
        app_log.setLevel("DEBUG")
    else:
        app_log.setLevel("INFO")
    app_log.info(f"Working directory is {os.getcwd()}")
    application = create_application(cmdline_args=args)
    application.listen(args["port"])
    ioloop.IOLoop.current().start()


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--service-prefix",
        "-s",
        default=os.environ.get("JUPYTERHUB_SERVICE_PREFIX", "/"),
        help="application API prefix",
    )
    parser.add_argument(
        "--port",
        "-p",
        default=8003,
        help="port for API to listen on",
        type=int
    )
    parser.add_argument(
        "--cookie-secret-file",
        required=True,
        help="Location of JupyterHub's cookie secret"
    )
    parser.add_argument(
        "--home-base-dir",
        required=True,
        help="Absolute path to the home directory location. Users` homes are derived as home-base-dir/username."
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Activate the debug logging level"
    )
    return vars(parser.parse_args())


def create_application(cmdline_args, **kwargs):
    with open(cmdline_args["cookie_secret_file"]) as f:
        text_secret = f.read().strip()
    cookie_secret = binascii.a2b_hex(text_secret)
    ProfileManager.home_base_dir = cmdline_args["home_base_dir"]
    prefix = cmdline_args["service_prefix"]
    return web.Application([(prefix, ProfileMakerHandler),
                            (urljoin(prefix, "profiles/(prof_[0-9]+)/data"), ProfileGetHandler, {'prefix': prefix}),
                            (urljoin(prefix, "profiles/create"), ProfileCreateHandler),
                            (urljoin(prefix, "profiles/(prof_[0-9]+)/update"), ProfileUpdateHandler),
                            (urljoin(prefix, "profiles/(prof_[0-9]+)/delete"), ProfileDeleteHandler),
                            (urljoin(prefix, "oauth_callback"), HubOAuthCallbackHandler),
                           ],
                           cookie_secret=cookie_secret,
                           template_path="templates",
                           login_url="/hub/login")


if __name__ == "__main__":
    main()
