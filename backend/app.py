from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
import random
import os

app = Flask(__name__)
CORS(app)

# Path to frontend folder
FRONTEND_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "frontend"
)

# Network state
network = {
    "throughput": 82,
    "latency": 28,
    "packet_loss": 4.7,
    "connections": 120,

    "link12": 87,
    "link13": 34,
    "link23": 52,

    "status": "NORMAL",
    "path": "S1 → S2"
}


# =========================
# HOME / DASHBOARD
# =========================

@app.route("/")
def home():
    return send_from_directory(
        FRONTEND_FOLDER,
        "index.html"
    )


# =========================
# FRONTEND PAGES
# =========================

@app.route("/<path:filename>")
def frontend_files(filename):

    return send_from_directory(
        FRONTEND_FOLDER,
        filename
    )


# =========================
# NETWORK API
# =========================

@app.route("/api/network")
def network_data():

    # Simulate real-time network changes
    network["throughput"] = random.randint(70, 95)

    network["latency"] = random.randint(20, 50)

    network["packet_loss"] = round(
        random.uniform(1.5, 5.5),
        1
    )

    network["connections"] = random.randint(
        100,
        150
    )

    # Simulate link utilization
    network["link12"] = random.randint(
        60,
        95
    )

    network["link13"] = random.randint(
        20,
        60
    )

    network["link23"] = random.randint(
        30,
        70
    )

    # Detect congestion
    if network["link12"] >= 85:

        network["status"] = "CONGESTION DETECTED"

        network["path"] = "S1 → S3"

    else:

        network["status"] = "NORMAL"

        network["path"] = "S1 → S2"

    return jsonify(network)


# =========================
# RUN SERVER
# =========================

if __name__ == "__main__":

    print("--------------------------------------")
    print(" SDN CAMPUS NETWORK BACKEND")
    print("--------------------------------------")
    print("Local server:")
    print("http://127.0.0.1:5000")
    print("--------------------------------------")

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )