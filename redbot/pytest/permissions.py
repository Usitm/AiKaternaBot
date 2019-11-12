# -*- coding: utf-8 -*-
# Red Dependencies
import pytest

# Red Imports
from redbot.cogs.permissions import Permissions
from redbot.core import Config


@pytest.fixture()
def permissions(config, monkeypatch, red):
    with monkeypatch.context() as m:
        m.setattr(Config, "get_conf", lambda *args, **kwargs: config)
        return Permissions(red)
