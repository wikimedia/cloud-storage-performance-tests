import React from 'react';
import { Report } from '../../types';
import { makeStyles } from '@material-ui/core';

const useStyles = makeStyles(() => ({
    selectReport: {
        position: 'absolute',
        left: '500px',
        fontSize: '100px',
    },
    progress: {
        position: 'absolute',
        top: 50,
        left: 500,
        zIndex: 0,
        width: '50%',
    },
    detailsRoot: {
        position: "absolute",
        left: 50,
        height: '100%',
        width: '100%',
    },
    iframe: {
        height: '100%',
        zIndex: 5,
        width: '100%',
        position: "absolute",
    },
}));

export function ReportDetails(props: { report: Report | null | undefined }): JSX.Element {
    const classes = useStyles();

    if (props.report == undefined || props.report === null) {
        return <div className={classes.selectReport}>Select a report.</div>;
    }
    return (
        <div className={classes.detailsRoot}>
            <div className={classes.progress}>Loading... hold your unicorns</div>
            <iframe className={classes.iframe} src={props.report.url} />
        </div>
    );
}
