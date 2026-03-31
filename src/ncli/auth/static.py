import os

from ncli.auth.base import AuthPlugin, Credentials


class StaticAuth(AuthPlugin):
    def resolve(self, device_name: str, device_config: dict) -> Credentials:
        auth_block = device_config.get("auth", {})
        auth_type = auth_block.get("type", "password")

        username = device_config.get("username", "")
        password = None
        key_file = None
        use_ssh_agent = False
        enable_secret = None

        if auth_type == "password":
            username = auth_block.get("username", username)
            password = auth_block.get("password")
            enable_secret = auth_block.get("enable_secret")
        elif auth_type == "ssh_key":
            username = auth_block.get("username", username)
            key_file = auth_block.get("key_file")
            if key_file is None:
                use_ssh_agent = True
            enable_secret = auth_block.get("enable_secret")
        else:
            raise ValueError(f"Device '{device_name}': unknown auth type '{auth_type}'")

        # Env var overrides always win
        if env_user := os.environ.get("NCLI_USERNAME"):
            username = env_user
        if env_pass := os.environ.get("NCLI_PASSWORD"):
            password = env_pass
        if env_enable := os.environ.get("NCLI_ENABLE_SECRET"):
            enable_secret = env_enable

        return Credentials(
            username=username,
            password=password,
            key_file=key_file,
            use_ssh_agent=use_ssh_agent,
            enable_secret=enable_secret,
        )
