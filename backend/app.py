from flask import Flask, jsonify, send_from_directory, send_file
from flask_cors import CORS

import io
import json
import os
import re
import subprocess
import threading
import time
from datetime import datetime

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
# FRONTEND FOLDER
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
    "gateway": "",
    "latency": 0,
    "link12": 0,
    "link13": 0,
    "link23": 0,
    "packet_loss": 0.0,
    "path": "Host Network",
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
# PREVIOUS VALUES FOR THROUGHPUT
# =========================================================

previous_stats = {
    "interface": None,
    "time": None,
    "total_bytes": None
}


# =========================================================
# ACTIVE CONNECTION CACHE
# =========================================================

active_connection = {
    "interface": None,
    "gateway": None,
    "last_check": 0
}


# =========================================================
# FIND ACTIVE INTERNET-CONNECTED INTERFACE
# =========================================================

def find_active_connection(force=False):
    global active_connection

    now = time.time()

    # Reuse the detected adapter for 10 seconds.
    # This avoids repeatedly starting PowerShell.
    if (
        not force
        and active_connection["interface"]
        and active_connection["gateway"]
        and (now - active_connection["last_check"] < 10)
    ):
        return (
            active_connection["interface"],
            active_connection["gateway"]
        )

    powershell_script = r'''
$config = Get-NetIPConfiguration |
    Where-Object {
        $_.NetAdapter.Status -eq "Up" -and
        $_.IPv4DefaultGateway -ne $null
    } |
    Select-Object -First 1

if ($null -eq $config) {
    Write-Output '{"Error":"NO_ACTIVE_ADAPTER"}'
    exit
}

$result = [PSCustomObject]@{
    Interface = $config.InterfaceAlias
    Gateway = $config.IPv4DefaultGateway.NextHop
}

$result | ConvertTo-Json -Compress
'''

    command = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        powershell_script
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        if result.returncode != 0:
            raise RuntimeError(
                result.stderr.strip()
                or "Active adapter detection failed."
            )

        output = result.stdout.strip()

        if not output:
            raise RuntimeError(
                "No active adapter information returned."
            )

        data = json.loads(output)

        if data.get("Error"):
            raise RuntimeError(data["Error"])

        interface_name = data.get("Interface", "")
        gateway = data.get("Gateway", "")

        if not interface_name:
            raise RuntimeError(
                "Active interface name not found."
            )

        active_connection["interface"] = interface_name
        active_connection["gateway"] = gateway
        active_connection["last_check"] = now

        return interface_name, gateway

    except Exception as error:
        print("Active adapter detection error:", error)

        return (
            active_connection["interface"],
            active_connection["gateway"]
        )


# =========================================================
# READ WINDOWS NETWORK STATISTICS
# =========================================================

def read_windows_network(interface_name):

    # Escape double quotes just in case.
    safe_interface = interface_name.replace('"', '""')

    powershell_script = f'''
$stats = Get-NetAdapterStatistics -Name "{safe_interface}" |
    Select-Object `
        Name,
        ReceivedBytes,
        SentBytes,
        ReceivedUnicastPackets,
        SentUnicastPackets,
        ReceivedPacketErrors,
        OutboundPacketErrors,
        ReceivedDiscardedPackets,
        OutboundDiscardedPackets

$stats | ConvertTo-Json -Compress
'''

    command = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        powershell_script
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=20,
        creationflags=subprocess.CREATE_NO_WINDOW
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip()
            or "Network statistics query failed."
        )

    output = result.stdout.strip()

    if not output:
        raise RuntimeError(
            "No network statistics returned."
        )

    return json.loads(output)


# =========================================================
# REAL LATENCY
# =========================================================

def get_real_latency(gateway):

    if not gateway:
        return 0

    try:
        # Ping the active network gateway once.
        result = subprocess.run(
            [
                "ping",
                "-n",
                "1",
                "-w",
                "1000",
                gateway
            ],
            capture_output=True,
            text=True,
            timeout=3,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        output = result.stdout

        # Examples:
        # time=3ms
        # time<1ms
        match = re.search(
            r"time[=<]\s*(\d+)\s*ms",
            output,
            re.IGNORECASE
        )

        if match:
            return int(match.group(1))

        # Windows may show <1ms.
        if re.search(
            r"time<1ms",
            output,
            re.IGNORECASE
        ):
            return 1

        return 0

    except Exception as error:
        print("Latency measurement error:", error)
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

        interface_name, gateway = find_active_connection()

        if not interface_name:
            raise RuntimeError(
                "No active Internet-connected adapter."
            )

        # -------------------------------------------------
        # WINDOWS COUNTERS
        # -------------------------------------------------

        stats = read_windows_network(interface_name)

        now = time.time()

        received_bytes = int(
            stats.get("ReceivedBytes", 0)
        )

        sent_bytes = int(
            stats.get("SentBytes", 0)
        )

        total_bytes = (
            received_bytes +
            sent_bytes
        )

        received_packets = int(
            stats.get(
                "ReceivedUnicastPackets",
                0
            )
        )

        sent_packets = int(
            stats.get(
                "SentUnicastPackets",
                0
            )
        )

        receive_errors = int(
            stats.get(
                "ReceivedPacketErrors",
                0
            )
        )

        send_errors = int(
            stats.get(
                "OutboundPacketErrors",
                0
            )
        )

        received_discards = int(
            stats.get(
                "ReceivedDiscardedPackets",
                0
            )
        )

        sent_discards = int(
            stats.get(
                "OutboundDiscardedPackets",
                0
            )
        )

        # -------------------------------------------------
        # THROUGHPUT
        # -------------------------------------------------

        throughput = 0.0

        # Adapter changed
        if previous_stats["interface"] != interface_name:

            previous_stats["interface"] = interface_name
            previous_stats["time"] = now
            previous_stats["total_bytes"] = total_bytes

        else:

            previous_time = previous_stats["time"]
            previous_bytes = previous_stats["total_bytes"]

            if (
                previous_time is not None
                and previous_bytes is not None
            ):

                elapsed = now - previous_time

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
        # REAL LATENCY
        # -------------------------------------------------

        latency = get_real_latency(gateway)

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

        elif latency > 100 and latency != 0:
            status = "HIGH LATENCY"

        elif throughput >= 50:
            status = "HIGH ACTIVITY"

        else:
            status = "NORMAL"

        # -------------------------------------------------
        # DATA
        # -------------------------------------------------

        new_data = {

            "connections": 0,

            "interface": interface_name,

            "gateway": gateway,

            "latency": latency,

            # Logical SDN links.
            # These are controlled by the
            # QoS/topology demonstration pages.
            "link12": 0,
            "link13": 0,
            "link23": 0,

            "packet_loss": packet_loss,

            "path": "Host Network",

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
            network_cache.update(new_data)

        print(
            "Network updated:",
            interface_name,
            "| Gateway:",
            gateway,
            "| Latency:",
            latency,
            "ms",
            "| Throughput:",
            round(throughput, 2),
            "Mbps"
        )

    except Exception as error:

        print(
            "Network monitor error:",
            error
        )

        # Keep previous good values.
        with cache_lock:

            if network_cache["interface"] == "Detecting...":
                network_cache["status"] = "MONITORING ERROR"


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

        elapsed = time.time() - start

        # Approximately every 2 seconds.
        sleep_time = max(
            0.5,
            2.0 - elapsed
        )

        time.sleep(sleep_time)


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
# FAST NETWORK API
# =========================================================

@app.route("/api/network")
def network_data():

    # The web page receives cached data immediately.
    # No PowerShell or ping is started here.

    with cache_lock:
        data = network_cache.copy()

    return jsonify(data)


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
        textColor=colors.HexColor("#087EA4")
    )

    section_style = ParagraphStyle(
        "SectionStyle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#087EA4"),
        spaceBefore=3,
        spaceAfter=8
    )

    body_style = ParagraphStyle(
        "BodyStyle",
        parent=styles["BodyText"],
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#222222"),
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
    # REPORT TITLE
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
            "REAL NETWORK MONITORING REPORT",
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
    # GENERAL INFO
    # -----------------------------------------------------

    info = [

        [
            Paragraph(
                "<b>MONITORING MODE</b>",
                small_style
            ),
            Paragraph(
                "REAL HOST NETWORK",
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
                "<b>GATEWAY</b>",
                small_style
            ),
            Paragraph(
                str(data["gateway"]),
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
                colors.HexColor("#8999A5")
            ),

            (
                "BACKGROUND",
                (0, 0),
                (0, -1),
                colors.HexColor("#EAF4F8")
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

    story.append(info_table)

    story.append(PageBreak())

    # -----------------------------------------------------
    # REAL NETWORK STATISTICS
    # -----------------------------------------------------

    story.append(
        Paragraph(
            "1. Real Network Statistics",
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
                "Gateway",
                small_style
            ),

            Paragraph(
                str(data["gateway"]),
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
                    data["receive_errors"] +
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
                    data["received_discards"]
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
                    data["sent_discards"]
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
                colors.HexColor("#8999A5")
            ),

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#087EA4")
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

    story.append(metrics_table)

    story.append(PageBreak())

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
            "S1, S2 and S3 represent the logical SDN "
            "demonstration topology used for QoS, "
            "congestion detection and dynamic load balancing.",
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
                colors.HexColor("#8999A5")
            ),

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#087EA4")
            ),

            (
                "TEXTCOLOR",
                (0, 0),
                (-1, 0),
                colors.white
            )
        ])
    )

    story.append(sdn_table_obj)

    story.append(PageBreak())

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
            "The application monitors the physical network "
            "connection used by the laptop and measures "
            "real-time traffic statistics and latency to "
            "the active network gateway. The logical S1/S2/S3 "
            "layer is used separately to demonstrate QoS "
            "and dynamic traffic management.",
            body_style
        )
    )

    story.append(
        Paragraph(
            "The latency value is the latest real round-trip "
            "response time measured from the laptop to the "
            "currently active network gateway.",
            body_style
        )
    )

    document.build(story)

    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name="SDN_Real_Network_Report.pdf",
        mimetype="application/pdf"
    )


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":

    print("--------------------------------------")
    print(" SDN CAMPUS NETWORK MONITOR")
    print("--------------------------------------")

    print(
        "Starting initial network detection..."
    )

    # First measurement before Flask starts.
    update_network_cache()

    # Start background monitor.
    monitor_thread = threading.Thread(
        target=network_monitor,
        daemon=True
    )

    monitor_thread.start()

    print(
        "Dashboard:"
    )

    print(
        "http://127.0.0.1:5000"
    )

    print("--------------------------------------")

    app.run(
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 5000)),
    debug=False,
    use_reloader=False
    )