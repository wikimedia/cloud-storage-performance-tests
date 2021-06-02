import React from 'react';
import { Report } from '../../types';
import { makeStyles } from '@material-ui/core';

const useStyles = makeStyles(() => ({
    selectReport: {
        position: "absolute",
        left: "500px",
        fontSize: "100px",
    },
    iframe: {
        height: "100%",
        width: "50%",
        flex: "auto",
    }
}))

export function ReportDetails(props: { report: Report | null | undefined }): JSX.Element {
    const classes = useStyles();

    if (props.report == undefined || props.report === null) {
        return <div className={classes.selectReport}>Select a report.</div>;
    }
    return <iframe className={classes.iframe} src={props.report.url}/>
}
