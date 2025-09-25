import argparse
import json
import subprocess
import os
import sys
import binascii

from tornado import escape, ioloop, web
from tornado.log import app_log

from jupyterhub.services.auth import HubOAuthenticated, HubOAuthCallbackHandler

class ProfileMakerHandler(HubOAuthenticated, web.RequestHandler):
    """Manage Profiles for JupyterHub wrapspawner"""

    def initialize(self, home_base_dir, **kwargs):
        self.home_base_dir = home_base_dir
        self.profiles = []

    @web.authenticated
    def prepare(self):
        self.user = self.get_current_user()
        app_log.info(f"Current user name is {self.user['name']}")
        self.user_profile_path = os.path.join(self.home_base_dir, self.user["name"], ".jupyterhub", "user_profiles.json")
        self.profiles = self._to_file('read')

    @web.authenticated
    def get(self):
        spawner_options = {"req_nprocs": "1", "req_memory": "100mb", "req_partition": "fastlane", "req_runtime": "00:10:00"}
        profile = {"description": "Test profile", "options": spawner_options}
        self._to_file('write', profile)
        self.render("page.html", base_url="/hub/")

    def _to_file(self, action, profile='{}'):
        """Handles interactions with JSON profile files"""
        if action == 'write' or action == 'delete':
            profile_json = json.dumps(profile)
        elif action == 'read':
            profile_json = ''
        else:
            raise ValueError("Action needs to be one of `read`, `write`, `delete`.")
        subproc_result = subprocess.run(
            [
                sys.executable,
                '-m', 'jupyterhub-profile-tool.userprofileworker',
                '--path', self.user_profile_path,
                '--action', action,
                profile_json
            ],
            text=True,
            user=self.user["name"])
        if subproc_result.returncode > 0:
            app_log.error(f"Errors encountered in subprocess: {subproc_result.stderr}")


def main():
    args = parse_arguments()
    app_log.info(f"Working directory is {os.getcwd()}")
    application = create_application(cmdline_args=args)
    application.listen(args["port"])
    ioloop.IOLoop.current().start()


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api-prefix",
        "-a",
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
    return vars(parser.parse_args())


def create_application(cmdline_args, handler=ProfileMakerHandler, **kwargs):
    with open(cmdline_args["cookie_secret_file"]) as f:
        text_secret = f.read().strip()
    cookie_secret = binascii.a2b_hex(text_secret)
    return web.Application([(cmdline_args["api_prefix"], handler, cmdline_args),
                            (os.path.join(cmdline_args["api_prefix"], 'oauth_callback'), HubOAuthCallbackHandler)],
                            cookie_secret=cookie_secret,
                            template_path='templates',
                            login_url='/hub/login')


if __name__ == "__main__":
    main()
