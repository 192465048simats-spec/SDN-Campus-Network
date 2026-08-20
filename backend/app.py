from flask import Flask, jsonify, send_from_directory, send_file
from flask_cors import CORS

import io
import os
import socket
import threading
import time
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
    "gateway": "Server Network",

    "latency": 0,

    "link12": 0,
    "link13": 0,
    "link23": 0,

    "packet_loss": 0.0,

    "path": "Render Server Network",

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
# LATENCY CACHE
# =========================================================

latency_cache = {
    "value": 0,
    "time": 0
}


# =========================================================
# GET ACTIVE SERVER INTERFACE
# =========================================================

def get_active_interface():

    try:

        counters = psutil.net_io_counters(pernic=True)

        if not counters:
            return "Server Network"

        best_interface = None
        best_total = 0

        for interface, stats in counters.items():

            total = (
                stats.bytes_sent +
                stats.bytes_recv
            )

            if total > best_total:

                best_total = total
                best_interface = interface

        if best_interface:
            return best_interface

        return "Server Network"

    except Exception as error:

        print(
            "Interface detection error:",
            error
        )

        return "Server Network"


# =========================================================
# GET NETWORK STATISTICS
# =========================================================

def read_network_statistics():

    counters = psutil.net_io_counters(
        pernic=True
    )

    interface_name = get_active_interface()

    stats = counters.get(
        interface_name
    )

    if stats is None:

        stats = psutil.net_io_counters()

    return interface_name, stats


# =========================================================
# REAL SERVER LATENCY
# =========================================================

def get_real_latency():

    """
    Measures real TCP connection time from the
    Render server to a public Internet endpoint.

    This does NOT depend on the user's laptop.
    """

    targets = [
        ("1.1.1.1", 443),
        ("8.8.8.8", 443)
    ]

    for host, port in targets:

        try:

            start = time.perf_counter()

            sock = socket.create_connection(
                (host, port),
                timeout=2
            )

            sock.close()

            elapsed = (
                time.perf_counter() -
                start
            )

            return round(
                elapsed * 1000,
                2
            )

        except Exception as error:

            print(
                "Latency test failed:",
                host,
                error
            )

    return 0


# =========================================================
# UPDATE NETWORK CACHE
# =========================================================

def update_network_cache():

    global previous_stats

    try:

        interface_name, stats = (
            read_network_statistics()
        )

        now = time.time()

        # -------------------------------------------------
        # BYTE COUNTERS
        # -------------------------------------------------

        received_bytes = int(
            stats.bytes_recv
        )

        sent_bytes = int(
            stats.bytes_sent
        )

        total_bytes = (
            received_bytes +
            sent_bytes
        )

        # -------------------------------------------------
        # PACKETS
        # -------------------------------------------------

        received_packets = int(
            stats.packets_recv
        )

        sent_packets = int(
            stats.packets_sent
        )

        # -------------------------------------------------
        # ERRORS
        # -------------------------------------------------

        receive_errors = int(
            stats.errin
        )

        send_errors = int(
            stats.errout
        )

        # -------------------------------------------------
        # DISCARDS
        # -------------------------------------------------

        received_discards = int(
            stats.dropin
        )

        sent_discards = int(
            stats.dropout
        )

        # -------------------------------------------------
        # THROUGHPUT
        # -------------------------------------------------

        throughput = 0.0

        if (
            previous_stats["time"] is not None
            and previous_stats["total_bytes"] is not None
        ):

            elapsed = (
                now -
                previous_stats["time"]
            )

            byte_difference = (
                total_bytes -
                previous_stats["total_bytes"]
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

        if (
            now -
            latency_cache["time"]
            >= 5
        ):

            latency = get_real_latency()

            latency_cache["value"] = latency
            latency_cache["time"] = now

        else:

            latency = latency_cache["value"]

        # -------------------------------------------------
        # PACKET LOSS
        # -------------------------------------------------

        total_packets = (
            received_packets +
            sent_packets
        )

        total_errors = (
            receive_errors +
            send_errors
        )

        if total_packets > 0:

            packet_loss = (
                total_errors /
                total_packets
            ) * 100

        else:

            packet_loss = 0.0

        packet_loss = round(
            min(packet_loss, 100),
            2
        )

        # -------------------------------------------------
        # CONNECTION COUNT
        # -------------------------------------------------

        try:

            connections = len(
                psutil.net_connections()
            )

        except Exception:

            connections = 0

        # -------------------------------------------------
        # STATUS
        # -------------------------------------------------

        if latency == 0:

            status = "NETWORK LIMITED"

        elif packet_loss >= 5:

            status = "ATTENTION REQUIRED"

        elif latency > 150:

            status = "HIGH LATENCY"

        elif throughput >= 50:

            status = "HIGH ACTIVITY"

        else:

            status = "NORMAL"

        # -------------------------------------------------
        # SDN LINK UTILIZATION
        # -------------------------------------------------

        # These represent the logical SDN
        # demonstration topology.

        utilization = min(
            round(
                throughput * 2,
                2
            ),
            100
        )

        link12 = utilization

        link13 = min(
            round(
                utilization * 0.75,
                2
            ),
            100
        )

        link23 = min(
            round(
                utilization * 0.50,
                2
            ),
            100
        )

        # -------------------------------------------------
        # NEW DATA
        # -------------------------------------------------

        new_data = {

            "connections": connections,

            "interface": interface_name,

            "gateway": "Render Internet Gateway",

            "latency": latency,

            "link12": link12,

            "link13": link13,

            "link23": link23,

            "packet_loss": packet_loss,

            "path": "Render Server Network",

            "receive_errors": receive_errors,

            "received_bytes": received_bytes,

            "received_discards": received_discards,

            "received_packets": received_packets,

            "send_errors": send_errors,

            "sent_bytes": sent_bytes,

            "sent_discards": sent_discards,

            "sent_packets": sent_packets,

            "status": status,

            "throughput": round(
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
            "NETWORK UPDATE |",
            "Interface:",
            interface_name,
            "| Latency:",
            latency,
            "ms",
            "| Throughput:",
            round(
                throughput,
                2
            ),
            "Mbps",
            "| Connections:",
            connections
        )

    except Exception as error:

        print(
            "Network monitor error:",
            error
        )

        with cache_lock:

            network_cache["status"] = (
                "MONITORING ERROR"
            )


# =========================================================
# BACKGROUND MONITOR
# =========================================================

def network_monitor():

    print(
        "Server network monitor started."
    )

    while True:

        start = time.time()

        update_network_cache()

        elapsed = (
            time.time() -
            start
        )

        time.sleep(
            max(
                1,
                2 - elapsed
            )
        )


# =========================================================
# FRONTEND ROUTES
# =========================================================

@app.route("/")
def home():

    return send_from_directory(
        FRONTEND_FOLDER,
        "index.html"
    )


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

@app.route("/api/health")
def health():

    return jsonify({
        "status": "online",
        "service": "SDN Campus Network",
        "server": "Render"
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
            20 * mm
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
            "REAL-TIME NETWORK MONITORING REPORT",
            ParagraphStyle(
                "Subtitle",
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
    # SERVER INFORMATION
    # -----------------------------------------------------

    info = [

        [
            Paragraph(
                "<b>MONITORING MODE</b>",
                small_style
            ),
            Paragraph(
                "RENDER SERVER NETWORK",
                small_style
            )
        ],

        [
            Paragraph(
                "<b>ACTIVE INTERFACE</b>",
                small_style
            ),
            Paragraph(
                str(data["interface"]),
                small_style
            )
        ],

        [
            Paragraph(
                "<b>NETWORK PATH</b>",
                small_style
            ),
            Paragraph(
                str(data["path"]),
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
            "1. Real-Time Network Statistics",
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
                str(data["interface"]),
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
                "Connections",
                small_style
            ),
            Paragraph(
                str(data["connections"]),
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
    # SDN LINKS
    # -----------------------------------------------------

    story.append(
        Paragraph(
            "2. SDN Demonstration Layer",
            section_style
        )
    )

    story.append(
        Paragraph(
            "S1, S2 and S3 represent the logical SDN "
            "topology used for QoS, congestion detection "
            "and dynamic load balancing.",
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
                "<b>UTILIZATION</b>",
                center_style
            )
        ],

        [
            Paragraph(
                "S1 → S2",
                small_style
            ),
            Paragraph(
                f"{data['link12']} %",
                small_style
            )
        ],

        [
            Paragraph(
                "S1 → S3",
                small_style
            ),
            Paragraph(
                f"{data['link13']} %",
                small_style
            )
        ],

        [
            Paragraph(
                "S2 → S3",
                small_style
            ),
            Paragraph(
                f"{data['link23']} %",
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
            "The deployed application measures network "
            "statistics from the Render server itself. "
            "It does not depend on the network adapter, "
            "PowerShell, gateway or operating system of "
            "the user's laptop.",
            body_style
        )
    )

    story.append(
        Paragraph(
            "The S1/S2/S3 layer represents the logical "
            "SDN demonstration topology used for QoS "
            "and dynamic traffic management.",
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
# STARTUP
# =========================================================

def start_monitor():

    thread = threading.Thread(
        target=network_monitor,
        daemon=True
    )

    thread.start()


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    print("--------------------------------------")
    print(" SDN CAMPUS NETWORK MONITOR")
    print("--------------------------------------")

    print(
        "Starting server network monitoring..."
    )

    update_network_cache()

    start_monitor()

    port = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    print(
        f"Starting Flask on port {port}"
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False
    )