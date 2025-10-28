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
from schema import Schema, And, Or, Use, Regex, Optional, SchemaError

from traitlets import HasTraits, Int, Unicode, Tuple

from jupyterhub.services.auth import HubOAuthenticated, HubOAuthCallbackHandler


class BaseProfileHandler(HubOAuthenticated, web.RequestHandler):
    """Base handler class for this program. Does the mixin of hub authentication, creates a ProfileManager instance in its prepare method."""

    @web.authenticated
    def prepare(self):
        self.user = self.get_current_user()
        self.manager_instance = ProfileManager(self.user["name"])


class ProfileMakerHandler(BaseProfileHandler):
    """Manage Profiles for JupyterHub wrapspawner"""

    def initialize(self, prefix):
        self.prefix = prefix

    def get(self):
        profiles = self.manager_instance.get_all_profiles()
        self.render("page.html", base_url="/hub/", user=self.user["name"], profiles=profiles, prefix=self.prefix, selected_profile="userprof_0")

    def post(self):
        spawner_options = {"req_nprocs": "1", "req_memory": "100M", "req_partition": "fastlane", "req_runtime": "00:10:00"}
        profile = {"description": "Test profile", "options": spawner_options}
        self.manager_instance.create_profile(profile)


class ProfileGetAllHandler(BaseProfileHandler):
    """Gets all profiles of the user"""

    def get(self):
        profiles = self.manager_instance.get_all_profiles()
        self.write(profiles)


class ProfileGetHandler(BaseProfileHandler):
    """Gets the user's profiles"""

    def get(self, profile_id):
        profile = self.manager_instance.get_singular_profile(profile_id)
        if profile is None:
            self.set_status(404)
            self.finish({"error": "Profile not found"})
            return
        self.write(profile)


class ProfileCreateHandler(BaseProfileHandler):
    """Creates an entirely new profile for the current user"""

    def post(self):
        data = self.request.body.decode("utf-8")
        try:
            self.manager_instance.create_profile(data)
            self.write({"status": "OK"})
        except SchemaError as e:
            self.set_status(400)
            self.write({"status": "error", "message": str(e)})


class ProfileUpdateHandler(BaseProfileHandler):
    """Updates a given profile for the current user"""

    def post(self, profile_id):
        data = self.request.body.decode('utf-8')
        try:
            self.manager_instance.update_profile(profile_id, data)
            self.write({"status": "OK"})
        except SchemaError as e:
            self.set_status(400)
            self.write({"status": "error", "message": str(e)})


class ProfileDeleteHandler(BaseProfileHandler):
    """Removes a profile for the current user"""

    def post(self, profile_id):
        self.manager_instance.delete_profile(profile_id)


class ProfileManager(HasTraits):
    """Performs the profile management in the background, keeping the Handlers simple
    Note on Interfaces: ProfileManager always returns payloads as Python objects including a string ID,
    but accepts both int and string IDs as well as Python object and string payloads.
    """

    class FileOpException(Exception):
        pass

    system_profile_path = Unicode(
        "/etc/jupyterhub/common_profiles.json",
        config=True
    )

    home_base_dir = Unicode(
        "/home/",
        config=True
    )

    allowed_partitions = Tuple(
        ("slowlane", "fastlane"),
        config=True
    )

    max_cpu_cores = Int(
        256,
        config=True
    )

    def __init__(self, username):
        app_log.debug(f"Instantiating profile manager for user {username}")
        self.username = username
        self.user_profile_path = os.path.join(self.home_base_dir, username, ".jupyterhub", "user_profiles.json")

    def __profile_id_to_index(self, profile_id):
        if profile_id.startswith("userprof_"):
            return int(profile_id.strip("userprof_")), True
        elif profile_id.startswith("sysprof_"):
            return int(profile_id.strip("sysprof_")), False
        else:
            raise ValueError(f"{profile_id} does not look like a known profile ID")

    def __index_to_profile_id(self, index, user=True):
        return f"userprof_{index}" if user else f"sysprof_{index}"

    def __ensure_stringified(self, profile_in):
        if isinstance(profile_in, dict) or isinstance(profile_in, list):
            profile_out = json.dumps(profile_in)
        elif isinstance(profile_in, str):
            # If `profile_in` is a string already, use it as-is.
            profile_out = profile_in
        else:
            raise ValueError(f"Unexpected profile representation: {type(profile_in)}. Cannot continue.")
        return profile_out

    def __ensure_objectified(self, profile_in):
        if isinstance(profile_in, str):
            try:
                profile_out = json.loads(profile_in)
            except json.JSONDecodeError as e:
                app_log.error(f"Could not parse JSON entries in string. Reported JSON error: {e}")
                profile_out = []
        elif isinstance(profile_in, dict) or isinstance(profile_in, list):
            # If `profile_in` is a python object already, use it as-is
            profile_out = profile_in
        else:
            raise ValueError(f"Unexpected profile representation: {type(profile_in)}. Cannot continue.")
        return profile_out

    def __generate_schema(self):
        profile_schema = Schema(
            {
                "description": And(str, lambda s: (len(s)>0 and not s.isspace()), error="Description is not a string, empty or consists only of spaces"),
                Optional("profile_id"): str,
                "options": {
                    "req_partition": Or(*self.allowed_partitions, error="Unknown partition"),
                    "req_runtime": Regex(r"^([0-9]-)?[0-9]{2}:[0-9]{2}:[0-9]{2}$", error="Malformed runtime specification"),
                    "req_nprocs": And(Use(str), lambda s: s.isdigit(), lambda s: (1 <= int(s) <= self.max_cpu_cores), error=f"Invalid nprocs spec, must be between 1 and {self.max_cpu_cores}"),
                    "req_memory": And(Regex(r"^[1-9][0-9]*\s*[kKmMgGtT]?[bB]?$", error="Malformed memory specification"), Use(lambda s: s.upper().replace(" ","").replace("B",""))),
                    Optional("req_gres"): Regex(r"^(gpu:((A40:)|(A100:))?[1-8])?$", error="Malformed GRES specification"),
                },
            }
        )
        return profile_schema

    def __sanitize(self, profile_in):
        schema = self.__generate_schema()
        if isinstance(profile_in, list):
            # Assume we have a list of profiles and call __sanitize recursively
            profile_out = []
            for element in profile_in:
                prof = schema.validate(element)
                # `profile_id` gets silently removed when sanitizing. Therefore, the calling function
                # must add it only after running this if it is required.
                prof.pop("profile_id", None)
                profile_out.append(prof)
        else:
            profile_out = schema.validate(profile_in)
            profile_out.pop("profile_id", None)
        return profile_out

    def __file_op(self, action, user=True, entry_index=None, new_profile=None):
        """Handles interactions with JSON profile files"""
        user_actions = ("read", "write", "delete", "update")
        system_actions = ("read")
        if user and action not in user_actions:
            raise ValueError(f"Allowed actions for user directory are {' '.join(user_actions)}.")
        elif not user and action not in system_actions:
            raise ValueError(f"Allowed actions for system directory are {' '.join(system_actions)}.")
        cmd = [
            sys.executable,
            "-m", "jupyterhub_profile_tool.userprofileworker",
            "--action", action,
            ]
        if user:
            cmd.extend(["--path", self.user_profile_path])
        else:
            cmd.extend(["--path", self.system_profile_path])
        if entry_index is not None:
            cmd.extend(["--entry_index", str(entry_index)])
        if new_profile is not None:
            cmd.append(new_profile)
        app_log.debug(f"Full command: {' '.join(cmd)}")
        subproc_result = subprocess.run(cmd, capture_output=True, text=True, user=self.username if user else None)
        # When reporting problems in the subproc, we assume a two-stage approach.
        # If it returns an RC > 0, we assume something went seriously wrong and error out.
        # If it has an error output, but no non-normal RC, we forward the message as a warning, but continue.
        if subproc_result.returncode > 0:
            app_log.error(f"Errors encountered in subprocess: {subproc_result.stderr}")
            raise self.FileOpException()
        elif subproc_result.stderr != "":
            app_log.warning(f"Problems encountered in subprocess: {subproc_result.stderr}")
        if action == "read":
            app_log.debug(f"Full subprocess output: {subproc_result.stdout}")
            return subproc_result.stdout

    def _get_profiles(self, user=True):
        str_profiles = self.__file_op("read", user=user)
        profiles = self.__ensure_objectified(str_profiles)
        try:
            profiles = self.__sanitize(profiles)
        except SchemaError as e:
            app_log.error(f"Loaded {'user' if user else 'system'} profiles look to be malformed. Schema says `{e}`. Returning empty list to not break anything.")
            profiles = []
        app_log.debug(f"{'User' if user else 'System'} profile data structure is {profiles}")
        for index, profile in enumerate(profiles):
            if isinstance(profile, dict):
                profile["profile_id"] = self.__index_to_profile_id(index, user)
            else:
                app_log.error(f"Unexpected non-dict element encountered: Type {type(profile)}, content {profile}")
        return profiles

    def create_profile(self, profile_in):
        profile_obj = self.__ensure_objectified(profile_in)
        try:
            profile_obj = self.__sanitize(profile_obj)
        except SchemaError as e:
            app_log.error(f"Schema evaluation for new profile failed. Schema says `{e}`. Stopping to avoid damage.")
            raise e
        profile_str = self.__ensure_stringified(profile_obj)
        self.__file_op("write", new_profile=profile_str)

    def update_profile(self, profile_id, new_profile_in):
        old_profile_index, user = self.__profile_id_to_index(profile_id)
        if not user:
            app_log.error("Tried to update a system profile. This should not be attempted. Refusing.")
            return
        new_profile_obj = self.__ensure_objectified(new_profile_in)
        try:
            new_profile_obj = self.__sanitize(new_profile_obj)
        except SchemaError as e:
            app_log.error(f"Schema evaluation for updated profile (index {old_profile_index}) failed. Schema says `{e}`. Stopping to avoid damage.")
            raise e
        new_profile_str = self.__ensure_stringified(new_profile_obj)
        self.__file_op("update", entry_index=old_profile_index, new_profile=new_profile_str)

    def delete_profile(self, profile_id):
        old_profile_index, user = self.__profile_id_to_index(profile_id)
        if not user:
            app_log.error("Tried to delete a system profile. This should not be attempted. Refusing.")
            return
        self.__file_op("delete", entry_index=old_profile_index)

    def get_all_profiles(self):
        user_profiles = self._get_profiles(user=True)
        system_profiles = self._get_profiles(user=False)
        return user_profiles + system_profiles

    def get_singular_profile(self, profile_id):
        index, user = self.__profile_id_to_index(profile_id)
        profiles = self._get_profiles(user)
        return profiles[index]


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
    app_log.debug(f"Using service prefix {prefix}")
    return web.Application([(prefix, ProfileMakerHandler, {"prefix": prefix}),
                            (urljoin(prefix, "profiles/data"), ProfileGetAllHandler),
                            (urljoin(prefix, "profiles/create"), ProfileCreateHandler),
                            (urljoin(prefix, "profiles/(userprof_[0-9]+)/data"), ProfileGetHandler),
                            (urljoin(prefix, "profiles/(sysprof_[0-9]+)/data"), ProfileGetHandler),
                            (urljoin(prefix, "profiles/(userprof_[0-9]+)/update"), ProfileUpdateHandler),
                            (urljoin(prefix, "profiles/(userprof_[0-9]+)/delete"), ProfileDeleteHandler),
                            (urljoin(prefix, "oauth_callback"), HubOAuthCallbackHandler),
                           ],
                           cookie_secret=cookie_secret,
                           template_path="templates",
                           login_url="/hub/login")


if __name__ == "__main__":
    main()
