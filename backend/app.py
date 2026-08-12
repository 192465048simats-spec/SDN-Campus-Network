from flask import Flask, jsonify, send_from_directory, send_file
from flask_cors import CORS

import random
import os
import io
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak
)


app = Flask(__name__)
CORS(app)


# =========================================================
# FRONTEND LOCATION
# =========================================================

FRONTEND_FOLDER = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "frontend"
)


# =========================================================
# NETWORK STATE
# =========================================================

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


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return send_from_directory(
        FRONTEND_FOLDER,
        "index.html"
    )


# =========================================================
# FRONTEND PAGES
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

    if network["link12"] >= 85:

        network["status"] = "CONGESTION DETECTED"
        network["path"] = "S1 → S3"

    else:

        network["status"] = "NORMAL"
        network["path"] = "S1 → S2"

    return jsonify(network)


# =========================================================
# REPORT HELPERS
# =========================================================

def utilization_status(value):

    if value >= 85:
        return "HIGH"

    elif value >= 60:
        return "MODERATE"

    return "NORMAL"


def security_status():

    if network["status"] == "CONGESTION DETECTED":
        return "ATTENTION REQUIRED"

    elif network["packet_loss"] >= 4.5:
        return "MONITOR"

    return "HEALTHY"


def security_assessment():

    if network["status"] == "CONGESTION DETECTED":

        return (
            "High link utilization has been detected on the "
            "primary network path. Traffic has been redirected "
            "to the alternate recommended route to maintain "
            "network availability and reduce congestion."
        )

    elif network["packet_loss"] >= 4.5:

        return (
            "Packet loss is slightly elevated. Continuous "
            "monitoring is recommended to identify abnormal "
            "traffic conditions and maintain network quality."
        )

    return (
        "The network is operating within the observed "
        "normal range. Continuous monitoring remains "
        "recommended for maintaining network reliability."
    )


# =========================================================
# PAGE HEADER / FOOTER
# =========================================================

def add_page_header_footer(canvas, doc):

    canvas.saveState()

    width, height = A4

    # Header line
    canvas.setStrokeColor(
        colors.HexColor("#087EA4")
    )

    canvas.setLineWidth(0.7)

    canvas.line(
        18 * mm,
        height - 12 * mm,
        width - 18 * mm,
        height - 12 * mm
    )

    # Header
    canvas.setFont(
        "Helvetica-Bold",
        7
    )

    canvas.setFillColor(
        colors.HexColor("#087EA4")
    )

    canvas.drawString(
        18 * mm,
        height - 9 * mm,
        "SDN CAMPUS NETWORK SECURITY MONITORING SYSTEM"
    )

    # Footer line
    canvas.setStrokeColor(
        colors.HexColor("#B5B5B5")
    )

    canvas.line(
        18 * mm,
        12 * mm,
        width - 18 * mm,
        12 * mm
    )

    # Footer
    canvas.setFont(
        "Helvetica",
        7
    )

    canvas.setFillColor(
        colors.HexColor("#555555")
    )

    canvas.drawString(
        18 * mm,
        7 * mm,
        "Saveetha School of Engineering"
    )

    canvas.drawRightString(
        width - 18 * mm,
        7 * mm,
        f"Page {doc.page}"
    )

    canvas.restoreState()


# =========================================================
# PDF REPORT
# =========================================================

@app.route("/api/report")
def generate_report():

    # Get a fresh network state
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

    if network["link12"] >= 85:

        network["status"] = "CONGESTION DETECTED"
        network["path"] = "S1 → S3"

    else:

        network["status"] = "NORMAL"
        network["path"] = "S1 → S2"


    # Current values
    throughput = network["throughput"]
    latency = network["latency"]
    packet_loss = network["packet_loss"]
    connections = network["connections"]

    link12 = network["link12"]
    link13 = network["link13"]
    link23 = network["link23"]

    status = network["status"]
    path = network["path"]

    generated = datetime.now().strftime(
        "%d-%m-%Y %H:%M:%S"
    )


    # -----------------------------------------------------
    # PDF
    # -----------------------------------------------------

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
        textColor=colors.HexColor("#087EA4"),
        spaceAfter=5
    )


    subtitle_style = ParagraphStyle(
        "SubtitleStyle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#222222"),
        spaceAfter=12
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
        fontName="Helvetica",
        fontSize=9.5,
        leading=14,
        textColor=colors.HexColor("#222222"),
        spaceAfter=9
    )


    small_style = ParagraphStyle(
        "SmallStyle",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#222222")
    )


    center_style = ParagraphStyle(
        "CenterStyle",
        parent=small_style,
        alignment=TA_CENTER
    )


    cover_label = ParagraphStyle(
        "CoverLabel",
        parent=small_style,
        fontName="Helvetica-Bold",
        fontSize=8,
        textColor=colors.HexColor("#087EA4")
    )


    cover_value = ParagraphStyle(
        "CoverValue",
        parent=small_style,
        fontSize=9,
        leading=11
    )


    story = []


    # =====================================================
    # PAGE 1 - COVER
    # =====================================================

    story.append(
        Spacer(1, 28 * mm)
    )

    story.append(
        Paragraph(
            "SDN CAMPUS NETWORK",
            title_style
        )
    )

    story.append(
        Paragraph(
            "NETWORK MONITORING & SECURITY",
            subtitle_style
        )
    )

    story.append(
        Spacer(1, 12 * mm)
    )

    story.append(
        Paragraph(
            "<b>Official Network Performance and "
            "Security Assessment Report</b>",
            ParagraphStyle(
                "CoverMain",
                parent=body_style,
                fontSize=13,
                alignment=TA_CENTER
            )
        )
    )

    story.append(
        Spacer(1, 15 * mm)
    )


    student_data = [

        [
            Paragraph("INSTITUTION", cover_label),
            Paragraph(
                "SAVEETHA SCHOOL OF ENGINEERING",
                cover_value
            )
        ],

        [
            Paragraph("STUDENT NAME", cover_label),
            Paragraph(
                "POTHURAJU SAI CHARAN TEJ",
                cover_value
            )
        ],

        [
            Paragraph("REGISTER NUMBER", cover_label),
            Paragraph(
                "192465048",
                cover_value
            )
        ],

        [
            Paragraph("DEPARTMENT", cover_label),
            Paragraph(
                "BE.CSE.CYBER SECURITY",
                cover_value
            )
        ],

        [
            Paragraph("YEAR OF STUDY", cover_label),
            Paragraph(
                "3RD",
                cover_value
            )
        ],

        [
            Paragraph("REPORT DATE", cover_label),
            Paragraph(
                generated.split()[0],
                cover_value
            )
        ]

    ]


    student_table = Table(
        student_data,
        colWidths=[
            48 * mm,
            102 * mm
        ]
    )


    student_table.setStyle(
        TableStyle([

            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.6,
                colors.HexColor("#9AA8B5")
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
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                7
            ),

            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                7
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


    story.append(student_table)

    story.append(
        Spacer(1, 20 * mm)
    )

    story.append(
        Paragraph(
            "SOFTWARE DEFINED NETWORKING  •  "
            "NETWORK SECURITY  •  REAL-TIME MONITORING",
            ParagraphStyle(
                "CoverFooter",
                parent=small_style,
                alignment=TA_CENTER,
                fontSize=8,
                textColor=colors.HexColor("#087EA4")
            )
        )
    )

    story.append(PageBreak())


    # =====================================================
    # PAGE 2 - EXECUTIVE SUMMARY
    # =====================================================

    story.append(
        Paragraph(
            "1. Executive Summary",
            section_style
        )
    )


    story.append(
        Paragraph(
            "This report presents the current performance and "
            "security condition of the Software Defined Networking "
            "(SDN) campus network. The monitoring system "
            "continuously observes network throughput, latency, "
            "packet loss, active connections and individual link "
            "utilization.",
            body_style
        )
    )


    story.append(
        Paragraph(
            "The system also performs congestion detection and "
            "dynamically selects an alternative network path when "
            "the primary link experiences high utilization. This "
            "approach supports improved network availability, "
            "traffic management and security visibility.",
            body_style
        )
    )


    current_status = (
        "NETWORK OPERATING NORMALLY"
        if status == "NORMAL"
        else
        "NETWORK UNDER CONGESTION"
    )


    status_color = (
        colors.HexColor("#1BAA59")
        if status == "NORMAL"
        else
        colors.HexColor("#D83A3A")
    )


    status_table = Table(
        [
            [
                Paragraph(
                    "<b>CURRENT NETWORK STATUS</b>",
                    center_style
                )
            ],
            [
                Paragraph(
                    f"<b>{current_status}</b>",
                    ParagraphStyle(
                        "StatusText",
                        parent=center_style,
                        fontSize=15,
                        textColor=status_color
                    )
                )
            ]
        ],
        colWidths=[
            150 * mm
        ]
    )


    status_table.setStyle(
        TableStyle([

            (
                "BOX",
                (0, 0),
                (-1, -1),
                1,
                status_color
            ),

            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.HexColor("#EEF4F7")
            ),

            (
                "BACKGROUND",
                (0, 1),
                (-1, 1),
                colors.HexColor("#F8FAFB")
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                8
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                8
            )

        ])
    )


    story.append(status_table)

    story.append(
        Spacer(1, 12 * mm)
    )


    story.append(
        Paragraph(
            "Key Monitoring Findings",
            section_style
        )
    )


    findings = [

        "Network throughput is continuously monitored.",

        "Latency and packet loss are observed as quality indicators.",

        "Active connections provide an indication of current network load.",

        "Individual network links are monitored for congestion.",

        "Alternative routing is selected when the primary path becomes congested."

    ]


    for item in findings:

        story.append(
            Paragraph(
                "• " + item,
                body_style
            )
        )


    story.append(PageBreak())


    # =====================================================
    # PAGE 3 - PERFORMANCE + TOPOLOGY
    # =====================================================

    story.append(
        Paragraph(
            "2. Network Performance Metrics",
            section_style
        )
    )


    performance_data = [

        [
            Paragraph("<b>METRIC</b>", center_style),
            Paragraph("<b>CURRENT VALUE</b>", center_style),
            Paragraph("<b>STATUS</b>", center_style)
        ],

        [
            Paragraph("Throughput", small_style),
            Paragraph(
                f"{throughput} Mbps",
                small_style
            ),
            Paragraph("MONITORED", small_style)
        ],

        [
            Paragraph("Latency", small_style),
            Paragraph(
                f"{latency} ms",
                small_style
            ),
            Paragraph("MONITORED", small_style)
        ],

        [
            Paragraph("Packet Loss", small_style),
            Paragraph(
                f"{packet_loss} %",
                small_style
            ),
            Paragraph("MONITORED", small_style)
        ],

        [
            Paragraph("Active Connections", small_style),
            Paragraph(
                str(connections),
                small_style
            ),
            Paragraph("ACTIVE", small_style)
        ]

    ]


    performance_table = Table(
        performance_data,
        colWidths=[
            65 * mm,
            42 * mm,
            43 * mm
        ]
    )


    performance_table.setStyle(
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


    story.append(performance_table)

    story.append(
        Spacer(1, 12 * mm)
    )


    story.append(
        Paragraph(
            "The above metrics represent the latest simulated "
            "telemetry collected by the SDN campus monitoring "
            "system. These measurements provide a real-time "
            "view of network performance.",
            body_style
        )
    )


    story.append(
        Paragraph(
            "3. SDN Network Topology",
            section_style
        )
    )


    topology_data = [

        [
            Paragraph("<b>DEVICE</b>", center_style),
            Paragraph("<b>ROLE</b>", center_style),
            Paragraph("<b>CONNECTED PATH</b>", center_style)
        ],

        [
            Paragraph("S1", center_style),
            Paragraph("Core Switch", small_style),
            Paragraph(
                "S1 → S2 / S1 → S3",
                small_style
            )
        ],

        [
            Paragraph("S2", center_style),
            Paragraph("Access Switch", small_style),
            Paragraph(
                "S2 → S1 / S2 → S3",
                small_style
            )
        ],

        [
            Paragraph("S3", center_style),
            Paragraph("Access Switch", small_style),
            Paragraph(
                "S3 → S1 / S3 → S2",
                small_style
            )
        ]

    ]


    topology_table = Table(
        topology_data,
        colWidths=[
            30 * mm,
            50 * mm,
            70 * mm
        ]
    )


    topology_table.setStyle(
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


    story.append(topology_table)

    story.append(
        Spacer(1, 8 * mm)
    )


    story.append(
        Paragraph(
            "The network consists of a core switch and access "
            "switches with multiple communication paths. The SDN "
            "controller can dynamically manage traffic routing "
            "according to current network conditions.",
            body_style
        )
    )


    story.append(PageBreak())


    # =====================================================
    # PAGE 4 - LINK + QOS
    # =====================================================

    story.append(
        Paragraph(
            "4. Link Utilization Analysis",
            section_style
        )
    )


    link_data = [

        [
            Paragraph(
                "<b>NETWORK LINK</b>",
                center_style
            ),

            Paragraph(
                "<b>UTILIZATION</b>",
                center_style
            ),

            Paragraph(
                "<b>STATUS</b>",
                center_style
            )
        ],

        [
            Paragraph("S1 → S2", small_style),
            Paragraph(
                f"{link12} %",
                small_style
            ),
            Paragraph(
                utilization_status(link12),
                small_style
            )
        ],

        [
            Paragraph("S1 → S3", small_style),
            Paragraph(
                f"{link13} %",
                small_style
            ),
            Paragraph(
                utilization_status(link13),
                small_style
            )
        ],

        [
            Paragraph("S2 → S3", small_style),
            Paragraph(
                f"{link23} %",
                small_style
            ),
            Paragraph(
                utilization_status(link23),
                small_style
            )
        ]

    ]


    link_table = Table(
        link_data,
        colWidths=[
            60 * mm,
            45 * mm,
            45 * mm
        ]
    )


    link_table.setStyle(
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


    story.append(link_table)

    story.append(
        Spacer(1, 12 * mm)
    )


    story.append(
        Paragraph(
            "5. QoS & Dynamic Load Balancing",
            section_style
        )
    )


    qos_data = [

        [
            Paragraph(
                "<b>TRAFFIC TYPE</b>",
                center_style
            ),
            Paragraph(
                "<b>PRIORITY</b>",
                center_style
            )
        ],

        [
            Paragraph("VoIP", small_style),
            Paragraph("HIGH", small_style)
        ],

        [
            Paragraph("Video", small_style),
            Paragraph("HIGH", small_style)
        ],

        [
            Paragraph("Web", small_style),
            Paragraph("NORMAL", small_style)
        ],

        [
            Paragraph("Download", small_style),
            Paragraph("LOW", small_style)
        ]

    ]


    qos_table = Table(
        qos_data,
        colWidths=[
            75 * mm,
            75 * mm
        ]
    )


    qos_table.setStyle(
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
                6
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                6
            )

        ])
    )


    story.append(qos_table)

    story.append(
        Spacer(1, 8 * mm)
    )


    story.append(
        Paragraph(
            "The system assigns higher priority to delay-sensitive "
            "traffic such as VoIP and video. When congestion is "
            "detected on the primary route, the SDN system can "
            "select a lower-congestion alternative path.",
            body_style
        )
    )


    routing_data = [

        [
            Paragraph(
                "<b>ROUTING PARAMETER</b>",
                center_style
            ),

            Paragraph(
                "<b>CURRENT RESULT</b>",
                center_style
            )
        ],

        [
            Paragraph(
                "Current Network Status",
                small_style
            ),

            Paragraph(
                status,
                small_style
            )
        ],

        [
            Paragraph(
                "Recommended Traffic Path",
                small_style
            ),

            Paragraph(
                path,
                small_style
            )
        ],

        [
            Paragraph(
                "Primary Link Utilization",
                small_style
            ),

            Paragraph(
                f"{link12} %",
                small_style
            )
        ]

    ]


    routing_table = Table(
        routing_data,
        colWidths=[
            75 * mm,
            75 * mm
        ]
    )


    routing_table.setStyle(
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
                6
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                6
            )

        ])
    )


    story.append(routing_table)

    story.append(PageBreak())


    # =====================================================
    # PAGE 5 - SECURITY
    # =====================================================

    story.append(
        Paragraph(
            "6. Cybersecurity Assessment",
            section_style
        )
    )


    security_points = [

        "Continuous Monitoring: Network telemetry should be continuously monitored to identify abnormal traffic conditions.",

        "Congestion Detection: High-utilization links should be identified early to prevent service degradation.",

        "Traffic Prioritization: Critical traffic should receive appropriate QoS priority.",

        "Dynamic Routing: Alternative paths should be used when the primary route becomes congested.",

        "Security Visibility: SDN centralized control can improve network visibility and support security monitoring."

    ]


    for point in security_points:

        story.append(
            Paragraph(
                "• " + point,
                body_style
            )
        )


    security_data = [

        [
            Paragraph(
                "<b>SECURITY STATUS</b>",
                small_style
            ),

            Paragraph(
                f"<b>{security_status()}</b>",
                small_style
            )
        ],

        [
            Paragraph(
                "<b>ASSESSMENT</b>",
                small_style
            ),

            Paragraph(
                security_assessment(),
                small_style
            )
        ]

    ]


    security_table = Table(
        security_data,
        colWidths=[
            40 * mm,
            110 * mm
        ]
    )


    security_table.setStyle(
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
                "TOP"
            ),

            (
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                6
            ),

            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                6
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                6
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                6
            )

        ])
    )


    story.append(security_table)

    story.append(
        Spacer(1, 8 * mm)
    )


    story.append(
        Paragraph(
            "7. Security & Network Recommendations",
            section_style
        )
    )


    recommendations = [

        "Maintain continuous monitoring of network traffic.",

        "Investigate links with utilization above 85%.",

        "Use dynamic load balancing during congestion.",

        "Maintain QoS priority for critical applications.",

        "Monitor packet loss and latency trends.",

        "Integrate intrusion detection and prevention mechanisms.",

        "Maintain secure communication between SDN components.",

        "Regularly review network logs and security events."

    ]


    for index, item in enumerate(
        recommendations,
        start=1
    ):

        story.append(
            Paragraph(
                f"{index}. {item}",
                body_style
            )
        )


    story.append(
        Paragraph(
            "8. Conclusion",
            section_style
        )
    )


    story.append(
        Paragraph(
            "The SDN Campus Network Monitoring System provides a "
            "centralized approach for observing network performance, "
            "detecting congestion and dynamically managing traffic. "
            "The integration of real-time monitoring, QoS and load "
            "balancing improves network visibility and supports "
            "security-focused network administration.",
            body_style
        )
    )


    story.append(
        Paragraph(
            "The generated assessment demonstrates how SDN "
            "technologies can be used to improve campus network "
            "reliability, performance and cybersecurity awareness.",
            body_style
        )
    )


    story.append(
        Spacer(1, 5 * mm)
    )


    generated_data = [

        [
            Paragraph(
                "<b>REPORT GENERATED BY</b>",
                small_style
            ),

            Paragraph(
                "POTHURAJU SAI CHARAN TEJ",
                small_style
            )
        ],

        [
            Paragraph(
                "<b>REGISTER NUMBER</b>",
                small_style
            ),

            Paragraph(
                "192465048",
                small_style
            )
        ],

        [
            Paragraph(
                "<b>DEPARTMENT</b>",
                small_style
            ),

            Paragraph(
                "BE.CSE.CYBER SECURITY",
                small_style
            )
        ],

        [
            Paragraph(
                "<b>INSTITUTION</b>",
                small_style
            ),

            Paragraph(
                "SAVEETHA SCHOOL OF ENGINEERING",
                small_style
            )
        ],

        [
            Paragraph(
                "<b>GENERATED ON</b>",
                small_style
            ),

            Paragraph(
                generated,
                small_style
            )
        ]

    ]


    generated_table = Table(
        generated_data,
        colWidths=[
            45 * mm,
            105 * mm
        ]
    )


    generated_table.setStyle(
        TableStyle([

            (
                "BOX",
                (0, 0),
                (-1, -1),
                0.7,
                colors.HexColor("#087EA4")
            ),

            (
                "INNERGRID",
                (0, 0),
                (-1, -1),
                0.4,
                colors.HexColor("#AAB8C2")
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
                "LEFTPADDING",
                (0, 0),
                (-1, -1),
                6
            ),

            (
                "RIGHTPADDING",
                (0, 0),
                (-1, -1),
                6
            ),

            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                5
            ),

            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                5
            )

        ])
    )


    story.append(generated_table)

    story.append(
        Spacer(1, 7 * mm)
    )


    story.append(
        Paragraph(
            "END OF REPORT",
            ParagraphStyle(
                "EndReport",
                parent=center_style,
                fontName="Helvetica-Bold",
                fontSize=8,
                textColor=colors.HexColor("#087EA4")
            )
        )
    )


    # =====================================================
    # BUILD PDF
    # =====================================================

    document.build(
        story,
        onFirstPage=add_page_header_footer,
        onLaterPages=add_page_header_footer
    )


    buffer.seek(0)


    return send_file(
        buffer,
        as_attachment=True,
        download_name="SDN_Campus_Network_Security_Report.pdf",
        mimetype="application/pdf"
    )


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    print("--------------------------------------")
    print(" SDN CAMPUS NETWORK BACKEND")
    print("--------------------------------------")

    print("Server running on:")
    print("http://127.0.0.1:5000")

    print("--------------------------------------")

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )