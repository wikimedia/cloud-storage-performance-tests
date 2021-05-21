import React from 'react';
import { Report } from '../../types';

export function ReportDetails(props: { report: Report | null | undefined }): JSX.Element {
    if (props.report == undefined || props.report === null) {
        return <div>Select a report.</div>;
    }
    return <iframe style={{height: "100%", width: "50%", flex: "auto"}} src={props.report.url}/>
}
