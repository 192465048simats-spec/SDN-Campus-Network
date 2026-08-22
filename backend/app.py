from flask import Flask, jsonify, send_from_directory, send_file
from flask_cors import CORS

import io
import os
import platform
import socket
import subprocess
import threading
import time
import urllib.request
from datetime import datetime

import psutil

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak
)


# =========================================================
# FLASK
# =========================================================

app = Flask(__name__)
CORS(app)


# =========================================================
# FRONTEND
# =========================================================

FRONTEND_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "frontend"
)


# =========================================================
# NETWORK CACHE
# =========================================================

network_cache = {
    "connections": 0,
    "interface": "Detecting...",
    "gateway": "Server Internet",
    "latency": 0,
    "link12": 0,
    "link13": 0,
    "link23": 0,
    "packet_loss": 0.0,
    "path": "Server Network",
    "receive_errors": 0,
    "received_bytes": 0,
    "received_discards": 0,
    "received_packets": 0,
    "send_errors": 0,
    "sent_bytes": 0,
    "sent_discards": 0,
    "sent_packets": 0,
    "status": "STARTING",
    "throughput": 0.0
}


cache_lock = threading.Lock()


# =========================================================
# PREVIOUS NETWORK VALUES
# =========================================================

previous_stats = {
    "time": None,
    "total_bytes": None
}


# =========================================================
# FIND ACTIVE NETWORK INTERFACE
# =========================================================

def find_active_interface():

    try:

        # Create UDP socket.
        # No actual data is sent.
        sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_DGRAM
        )

        sock.settimeout(2)

        try:
            sock.connect(("8.8.8.8", 80))
            local_ip = sock.getsockname()[0]

        finally:
            sock.close()

        interfaces = psutil.net_if_addrs()
        interface_stats = psutil.net_if_stats()

        for interface_name, addresses in interfaces.items():

            if interface_name not in interface_stats:
                continue

            if not interface_stats[interface_name].isup:
                continue

            for address in addresses:

                if (
                    address.family == socket.AF_INET
                    and address.address == local_ip
                ):
                    return interface_name

        return "Internet"

    except Exception as error:

        print(
            "Interface detection error:",
            error
        )

        return "Internet"


# =========================================================
# GET NETWORK STATISTICS
# =========================================================

def get_network_statistics(interface_name):

    counters = psutil.net_io_counters(
        pernic=True
    )

    stats = counters.get(interface_name)

    if stats is None:

        # Fallback to all interfaces
        stats = psutil.net_io_counters()

    return {
        "received_bytes": int(
            stats.bytes_recv
        ),

        "sent_bytes": int(
            stats.bytes_sent
        ),

        "received_packets": int(
            stats.packets_recv
        ),

        "sent_packets": int(
            stats.packets_sent
        ),

        "receive_errors": int(
            stats.errin
        ),

        "send_errors": int(
            stats.errout
        ),

        "received_discards": int(
            stats.dropin
        ),

        "sent_discards": int(
            stats.dropout
        )
    }


# =========================================================
# INTERNET LATENCY
# =========================================================

def get_latency():

    # Try ping first
    try:

        system = platform.system().lower()

        if system == "windows":

            command = [
                "ping",
                "-n",
                "1",
                "-w",
                "1500",
                "1.1.1.1"
            ]

        else:

            command = [
                "ping",
                "-c",
                "1",
                "-W",
                "2",
                "1.1.1.1"
            ]

        start = time.time()

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0:

            latency = (
                time.time() - start
            ) * 1000

            return round(
                latency,
                2
            )

    except Exception:
        pass


    # Fallback: HTTPS request
    try:

        start = time.time()

        request = urllib.request.Request(
            "https://www.cloudflare.com/cdn-cgi/trace",
            method="GET"
        )

        with urllib.request.urlopen(
            request,
            timeout=5
        ):
            pass

        latency = (
            time.time() - start
        ) * 1000

        return round(
            latency,
            2
        )

    except Exception:

        return 0


# =========================================================
# UPDATE NETWORK CACHE
# =========================================================

def update_network_cache():

    global previous_stats

    try:

        # -------------------------------------------------
        # ACTIVE INTERFACE
        # -------------------------------------------------

        interface_name = find_active_interface()

        # -------------------------------------------------
        # NETWORK STATISTICS
        # -------------------------------------------------

        stats = get_network_statistics(
            interface_name
        )

        now = time.time()

        received_bytes = stats[
            "received_bytes"
        ]

        sent_bytes = stats[
            "sent_bytes"
        ]

        received_packets = stats[
            "received_packets"
        ]

        sent_packets = stats[
            "sent_packets"
        ]

        receive_errors = stats[
            "receive_errors"
        ]

        send_errors = stats[
            "send_errors"
        ]

        received_discards = stats[
            "received_discards"
        ]

        sent_discards = stats[
            "sent_discards"
        ]

        total_bytes = (
            received_bytes +
            sent_bytes
        )


        # -------------------------------------------------
        # THROUGHPUT
        # -------------------------------------------------

        throughput = 0.0

        previous_time = previous_stats[
            "time"
        ]

        previous_bytes = previous_stats[
            "total_bytes"
        ]

        if (
            previous_time is not None
            and previous_bytes is not None
        ):

            elapsed = (
                now -
                previous_time
            )

            byte_difference = (
                total_bytes -
                previous_bytes
            )

            if (
                elapsed > 0
                and byte_difference >= 0
            ):

                throughput = (
                    byte_difference * 8
                ) / elapsed / 1_000_000

        previous_stats["time"] = now
        previous_stats["total_bytes"] = total_bytes


        # -------------------------------------------------
        # LATENCY
        # -------------------------------------------------

        latency = get_latency()


        # -------------------------------------------------
        # PACKET ERROR RATE
        # -------------------------------------------------

        total_packets = (
            received_packets +
            sent_packets
        )

        total_errors = (
            receive_errors +
            send_errors
        )

        packet_loss = 0.0

        if total_packets > 0:

            packet_loss = (
                total_errors /
                total_packets
            ) * 100

        packet_loss = round(
            min(packet_loss, 100),
            2
        )


        # -------------------------------------------------
        # STATUS
        # -------------------------------------------------

        if packet_loss >= 5:

            status = "ATTENTION REQUIRED"

        elif latency > 200:

            status = "HIGH LATENCY"

        elif throughput >= 50:

            status = "HIGH ACTIVITY"

        else:

            status = "NORMAL"


        # -------------------------------------------------
        # NEW DATA
        # -------------------------------------------------

        new_data = {

            "connections": 0,

            "interface":
                interface_name,

            "gateway":
                "Server Internet",

            "latency":
                latency,

            # Logical SDN demonstration links
            "link12": 0,
            "link13": 0,
            "link23": 0,

            "packet_loss":
                packet_loss,

            "path":
                "Server Network",

            "receive_errors":
                receive_errors,

            "received_bytes":
                received_bytes,

            "received_discards":
                received_discards,

            "received_packets":
                received_packets,

            "send_errors":
                send_errors,

            "sent_bytes":
                sent_bytes,

            "sent_discards":
                sent_discards,

            "sent_packets":
                sent_packets,

            "status":
                status,

            "throughput":
                round(
                    throughput,
                    2
                )
        }


        # -------------------------------------------------
        # CACHE
        # -------------------------------------------------

        with cache_lock:

            network_cache.update(
                new_data
            )


        print(
            "Network updated:",
            interface_name,
            "| Latency:",
            latency,
            "ms",
            "| Throughput:",
            round(
                throughput,
                2
            ),
            "Mbps"
        )


    except Exception as error:

        print(
            "Network monitor error:",
            error
        )

        with cache_lock:

            network_cache[
                "status"
            ] = "MONITORING ERROR"


# =========================================================
# BACKGROUND MONITOR
# =========================================================

def network_monitor():

    print(
        "Background network monitor started."
    )

    while True:

        start = time.time()

        update_network_cache()

        elapsed = (
            time.time() -
            start
        )

        sleep_time = max(
            1,
            2.0 - elapsed
        )

        time.sleep(
            sleep_time
        )


# =========================================================
# HOME PAGE
# =========================================================

@app.route("/")
def home():

    return send_from_directory(
        FRONTEND_FOLDER,
        "index.html"
    )


# =========================================================
# FRONTEND FILES
# =========================================================

@app.route("/<path:filename>")
def frontend_files(filename):

    return send_from_directory(
        FRONTEND_FOLDER,
        filename
    )


# =========================================================
# NETWORK API
# =========================================================

@app.route("/api/network")
def network_data():

    with cache_lock:

        data = network_cache.copy()

    return jsonify(data)


# =========================================================
# HEALTH CHECK
# =========================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "online",
        "service": "SDN Campus Network Backend",
        "time": datetime.now().isoformat()
    })


# =========================================================
# PDF REPORT
# =========================================================

@app.route("/api/report")
def generate_report():

    with cache_lock:

        data = network_cache.copy()

    buffer = io.BytesIO()

    document = SimpleDocTemplate(

        buffer,

        pagesize=A4,

        rightMargin=18 * mm,

        leftMargin=18 * mm,

        topMargin=18 * mm,

        bottomMargin=18 * mm
    )

    styles = getSampleStyleSheet()


    title_style = ParagraphStyle(

        "TitleStyle",

        parent=styles["Title"],

        fontName="Helvetica-Bold",

        fontSize=19,

        leading=23,

        alignment=TA_CENTER,

        textColor=colors.HexColor(
            "#087EA4"
        )
    )


    section_style = ParagraphStyle(

        "SectionStyle",

        parent=styles["Heading2"],

        fontName="Helvetica-Bold",

        fontSize=13,

        leading=16,

        textColor=colors.HexColor(
            "#087EA4"
        ),

        spaceBefore=3,

        spaceAfter=8
    )


    body_style = ParagraphStyle(

        "BodyStyle",

        parent=styles["BodyText"],

        fontSize=9.5,

        leading=14,

        textColor=colors.HexColor(
            "#222222"
        ),

        spaceAfter=9
    )


    small_style = ParagraphStyle(

        "SmallStyle",

        parent=styles["BodyText"],

        fontSize=8,

        leading=10
    )


    center_style = ParagraphStyle(

        "CenterStyle",

        parent=small_style,

        alignment=TA_CENTER
    )


    story = []


    # -----------------------------------------------------
    # TITLE
    # -----------------------------------------------------

    story.append(
        Spacer(
            1,
            25 * mm
        )
    )


    story.append(
        Paragraph(
            "SDN CAMPUS NETWORK",
            title_style
        )
    )


    story.append(
        Paragraph(
            "NETWORK MONITORING REPORT",

            ParagraphStyle(
                "SubTitle",

                parent=body_style,

                alignment=TA_CENTER,

                fontSize=11
            )
        )
    )


    story.append(
        Spacer(
            1,
            12 * mm
        )
    )


    # -----------------------------------------------------
    # GENERAL INFORMATION
    # -----------------------------------------------------

    info = [

        [
            Paragraph(
                "<b>MONITORING MODE</b>",
                small_style
            ),

            Paragraph(
                "SERVER NETWORK",
                small_style
            )
        ],

        [
            Paragraph(
                "<b>ACTIVE INTERFACE</b>",
                small_style
            ),

            Paragraph(
                str(
                    data["interface"]
                ),
                small_style
            )
        ],

        [
            Paragraph(
                "<b>NETWORK</b>",
                small_style
            ),

            Paragraph(
                "Render Server Internet",
                small_style
            )
        ],

        [
            Paragraph(
                "<b>GENERATED</b>",
                small_style
            ),

            Paragraph(
                datetime.now().strftime(
                    "%d-%m-%Y %H:%M:%S"
                ),
                small_style
            )
        ]
    ]


    info_table = Table(

        info,

        colWidths=[
            50 * mm,
            100 * mm
        ]
    )


    info_table.setStyle(

        TableStyle([

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.6,
                colors.HexColor(
                    "#8999A5"
                )
            ),

            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor(
                    "#EAF4F8"
                )
            ),

            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                7
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                7
            )
        ])
    )


    story.append(
        info_table
    )


    story.append(
        PageBreak()
    )


    # -----------------------------------------------------
    # NETWORK STATISTICS
    # -----------------------------------------------------

    story.append(
        Paragraph(
            "1. Network Statistics",
            section_style
        )
    )


    metrics = [

        [
            Paragraph(
                "<b>METRIC</b>",
                center_style
            ),

            Paragraph(
                "<b>VALUE</b>",
                center_style
            )
        ],

        [
            Paragraph(
                "Active Interface",
                small_style
            ),

            Paragraph(
                str(
                    data["interface"]
                ),
                small_style
            )
        ],

        [
            Paragraph(
                "Latency",
                small_style
            ),

            Paragraph(
                f"{data['latency']} ms",
                small_style
            )
        ],

        [
            Paragraph(
                "Throughput",
                small_style
            ),

            Paragraph(
                f"{data['throughput']} Mbps",
                small_style
            )
        ],

        [
            Paragraph(
                "Packet Loss",
                small_style
            ),

            Paragraph(
                f"{data['packet_loss']} %",
                small_style
            )
        ],

        [
            Paragraph(
                "Received Packets",
                small_style
            ),

            Paragraph(
                f"{data['received_packets']:,}",
                small_style
            )
        ],

        [
            Paragraph(
                "Sent Packets",
                small_style
            ),

            Paragraph(
                f"{data['sent_packets']:,}",
                small_style
            )
        ],

        [
            Paragraph(
                "Packet Errors",
                small_style
            ),

            Paragraph(
                str(
                    data["receive_errors"]
                    +
                    data["send_errors"]
                ),
                small_style
            )
        ],

        [
            Paragraph(
                "Received Discards",
                small_style
            ),

            Paragraph(
                str(
                    data[
                        "received_discards"
                    ]
                ),
                small_style
            )
        ],

        [
            Paragraph(
                "Sent Discards",
                small_style
            ),

            Paragraph(
                str(
                    data[
                        "sent_discards"
                    ]
                ),
                small_style
            )
        ]
    ]


    metrics_table = Table(

        metrics,

        colWidths=[
            75 * mm,
            75 * mm
        ]
    )


    metrics_table.setStyle(

        TableStyle([

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.6,
                colors.HexColor(
                    "#8999A5"
                )
            ),

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor(
                    "#087EA4"
                )
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            ),

            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "MIDDLE"
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                7
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                7
            )
        ])
    )


    story.append(
        metrics_table
    )


    story.append(
        PageBreak()
    )


    # -----------------------------------------------------
    # SDN DEMONSTRATION
    # -----------------------------------------------------

    story.append(
        Paragraph(
            "2. SDN Demonstration Layer",
            section_style
        )
    )


    story.append(
        Paragraph(

            "S1, S2 and S3 represent the logical "
            "SDN topology used for QoS, congestion "
            "detection and dynamic load balancing.",

            body_style
        )
    )


    sdn_table = [

        [
            Paragraph(
                "<b>LINK</b>",
                center_style
            ),

            Paragraph(
                "<b>ROLE</b>",
                center_style
            )
        ],

        [
            Paragraph(
                "S1 → S2",
                small_style
            ),

            Paragraph(
                "Primary SDN path",
                small_style
            )
        ],

        [
            Paragraph(
                "S1 → S3",
                small_style
            ),

            Paragraph(
                "Alternate SDN path",
                small_style
            )
        ],

        [
            Paragraph(
                "S2 → S3",
                small_style
            ),

            Paragraph(
                "Secondary link",
                small_style
            )
        ]
    ]


    sdn_table_obj = Table(

        sdn_table,

        colWidths=[
            75 * mm,
            75 * mm
        ]
    )


    sdn_table_obj.setStyle(

        TableStyle([

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.6,
                colors.HexColor(
                    "#8999A5"
                )
            ),

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor(
                    "#087EA4"
                )
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            )
        ])
    )


    story.append(
        sdn_table_obj
    )


    story.append(
        PageBreak()
    )


    # -----------------------------------------------------
    # CONCLUSION
    # -----------------------------------------------------

    story.append(
        Paragraph(
            "3. Conclusion",
            section_style
        )
    )


    story.append(
        Paragraph(

            "The application monitors the network "
            "environment of the server running the "
            "SDN Campus Network application. The "
            "network statistics are collected using "
            "the cross-platform psutil library.",

            body_style
        )
    )


    story.append(
        Paragraph(

            "The S1/S2/S3 layer represents the logical "
            "SDN demonstration topology used to "
            "demonstrate QoS and dynamic traffic "
            "management concepts.",

            body_style
        )
    )


    document.build(
        story
    )


    buffer.seek(0)


    return send_file(

        buffer,

        as_attachment=True,

        download_name=(
            "SDN_Real_Network_Report.pdf"
        ),

        mimetype="application/pdf"
    )


# =========================================================
# START SERVER
# =========================================================
# =========================================================
# START BACKGROUND MONITOR FOR GUNICORN / RENDER
# =========================================================

monitor_started = False
monitor_start_lock = threading.Lock()


@app.before_request
def start_monitor_if_needed():
    global monitor_started

    if not monitor_started:
        with monitor_start_lock:
            if not monitor_started:
                print("Starting background network monitor...")
                
                monitor_thread = threading.Thread(
                    target=network_monitor,
                    daemon=True
                )

                monitor_thread.start()
                monitor_started = True

if __name__ == "__main__":

    print("--------------------------------------")
    print(" SDN CAMPUS NETWORK MONITOR")
    print("--------------------------------------")

    print(
        "Starting network detection..."
    )

    # First measurement
    update_network_cache()


    # Background monitor
    monitor_thread = threading.Thread(
        target=network_monitor,
        daemon=True
    )

    monitor_thread.start()


    print(
        "Dashboard server starting..."
    )

    print(
        "Port:",
        os.environ.get(
            "PORT",
            "5000"
        )
    )

    print("--------------------------------------")


    app.run(

        host="0.0.0.0",

        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),

        debug=False,

        use_reloader=False
    )