import argparse
import json
import subprocess
import os
import sys
import binascii

from tornado import escape, ioloop, web
from tornado.log import app_log

from jupyterhub.services.auth import HubOAuthenticated, HubOAuthCallbackHandler

cookie_secret_file = '/root/.jupyterhub_secrets/jupyterhub_cookie_secret'

class ProfileMakerHandler(HubOAuthenticated, web.RequestHandler):
    """Manage Profiles for JupyterHub wrapspawner"""

    home_base_dir = "/mnt/nfs/home"

    # @web.authenticated
    # def post(self):
    #     user = self.get_current_user()
    #     app_log.info("Current user name is %s", user["name"])
    #     user_profile_path = os.path.join(self.home_base_dir, user["name"], ".jupyterhub", "user_profile.json")
    #     app_log.info("Trying to write to %s", user_profile_path)
    #     spawner_options = {"req_nprocs": "1", "req_memory": "100mb", "req_partition": "fastlane", "req_runtime": "00:10:00"}
    #     profile = {"description": "Test profile", "options": spawner_options}
    #     self.write_to_file(profile, user_profile_path, user["name"])

    @web.authenticated
    def get(self):
        user = self.get_current_user()
        app_log.info("Current user name is %s", user["name"])
        user_profile_path = os.path.join(self.home_base_dir, user["name"], ".jupyterhub", "user_profile.json")
        app_log.info("Trying to write to %s", user_profile_path)
        spawner_options = {"req_nprocs": "1", "req_memory": "100mb", "req_partition": "fastlane", "req_runtime": "00:10:00"}
        profile = {"description": "Test profile", "options": spawner_options}
        self.write_to_file(profile, user_profile_path, user["name"])
        self.write("Hello world")

    def write_to_file(self, profile, user_profile_path, username):
        """Write dictionary document to file as JSON"""
        profile_json = json.dumps(profile)
        subprocess.run([sys.executable, '-m', 'jupyterhub-profile-tool.userprofileworker', '--path', user_profile_path, '--action', 'write', profile_json], user=username)


def main():
    args = parse_arguments()
    application = create_application(**vars(args))
    application.listen(args.port)
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
    return parser.parse_args()


def create_application(api_prefix="/", handler=ProfileMakerHandler, **kwargs):
    with open(cookie_secret_file) as f:
        text_secret = f.read().strip()
    cookie_secret = binascii.a2b_hex(text_secret)
    return web.Application([(api_prefix, handler),
                            (os.path.join(api_prefix, 'oauth_callback'), HubOAuthCallbackHandler)],
                            cookie_secret=cookie_secret)


if __name__ == "__main__":
    main()
