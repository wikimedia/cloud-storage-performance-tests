import React from 'react';
import { useEffect, useState } from 'react';
import { Report } from '../../types';
import { ReportDetails } from '../ReportDetails';
import './styles.css';

export function ReportsList(): JSX.Element {
    const [reports, setReports] = useState<Array<Report>>([]);
    const [report, setReport] = useState<Report>();

    useEffect(() => {
        fetch('api/v1/reports/')
            .then((res) => res.json())
            .then((data) => {
                setReports(data);
            });
    }, []);

    return (
        <div className="reports-list">
            <div className="reports-sidebar">
                <div className="reports-list-title">Available reports</div>
                <div className="report-bullets">
                    {reports.map((iter_report) => {
                        return (
                            <div
                                className={report && iter_report.url === report.url ? 'report-entry-name-selected' : 'report-entry-name'}
                                key={iter_report.url}
                                onClick={(elem) => {
                                    console.log(elem);
                                    setReport(iter_report);
                                }}
                            >
                                {iter_report.name}{' '}
                            </div>
                        );
                    })}
                </div>
            </div>
            <ReportDetails report={report} />
        </div>
    );
}
