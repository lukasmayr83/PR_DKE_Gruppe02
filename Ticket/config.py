import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = "dev-secret-key"  #
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(basedir, "instance", "tickets.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    STRECKEN_API_BASE = "http://127.0.0.1:5001"
    FAHRPLAN_API_BASE = "http://127.0.0.1:5002"
    FLOTTEN_API_BASE = "http://127.0.0.1:5003"
