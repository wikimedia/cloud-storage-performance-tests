#!/usr/bin/env python3
import os
from typing import List
from flask import Flask, jsonify, send_from_directory
from flasgger import Swagger
from dataclasses import dataclass


app = Flask(__name__, static_folder="../app/build/static")
swagger = Swagger(app)


if app.config["ENV"] == "production":
    STATIC_FILES_HOST = "https://tools-static.wmflabs.org"
    APP_BASE_PATH = "/cloud-ceph-performance-tests"

elif app.config["ENV"] == "development":
    STATIC_FILES_HOST = "http://localhost:5000"
    APP_BASE_PATH = ""


@dataclass(frozen=True)
class Report:
    date: str
    url: str
    name: str


def _load_reports(report_path: str = "../reports") -> List[Report]:
    reports: List[Report] = []
    report_path = os.path.realpath(os.path.expanduser(report_path))
    (type_dirs_path, type_dirs, _) = next(os.walk(report_path))
    for report_type in type_dirs:
        (_, _, report_files) = next(os.walk(os.path.join(type_dirs_path, report_type)))
        for report_file in report_files:
            report_name = report_file.split(".html", 1)[0]
            report_date = report_name.split("_", 1)[0]
            if not report_date.startswith("20"):
                report_date = ""

            report_url = f"{STATIC_FILES_HOST}{APP_BASE_PATH}/reports/{report_type}/{report_file}"
            if report_url.endswith(".html.gz"):
                report_url = report_url.rsplit(".", 1)[0]
            reports.append(
                Report(
                    date=report_date,
                    name=report_name,
                    url=report_url,
                )
            )

    return reports


@app.route("/")
def index():
    return send_from_directory("../app/build/", "index.html")


@app.route("/api/v1/reports/")
def reports():
    """return all the currently available performance reports.
    This is using docstrings for specifications.
    ---
    parameters: []
    definitions:
      PerformanceReports:
        type: array
        items:
          $ref: '#/definitions/PerformanceReport'
      PerformanceReport:
        type: object
        properties:
          report_name:
            type: string
          url:
            type: string
          date:
            type: string
    responses:
      200:
        description: A list of reports
        schema:
          $ref: '#/definitions/PerformanceReports'
        examples:
    """

    return jsonify(_load_reports())


@app.route("/reports/<path:path>")
def get_report(path: str):
    full_gz_path = f"../reports/{path}.gz"
    if os.path.exists(full_gz_path):
        response = send_from_directory("../reports", path + ".gz")
    else:
        response = send_from_directory("../reports", path)

    return response


if __name__ == "__main__":
    app.run()